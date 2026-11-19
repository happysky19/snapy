// torch
#include <ATen/Dispatch.h>
#include <ATen/TensorIterator.h>
#include <ATen/native/ReduceOpsUtils.h>
#include <ATen/native/cpu/Loops.h>
#include <torch/torch.h>

// snap
#include <snap/snap.h>

#include <snap/utils/on_host.hpp>

#include "riemann_dispatch.hpp"
#include "riemann_kernels.h"

namespace snap {
namespace {

// One CPU loop for every face-function kind: each face is
// riemann_face<K, C, E, W>, C when the iterator carries riemann.central, E
// when it carries roe's LLF flag, W when it carries the wave speed.
template <RiemannKind K, bool C, bool E, bool W>
void riemann_cpu_loop(at::TensorIterator& iter, int dim,
                      RiemannParams const& params,
                      torch::Tensor const& inv_mu_ratio_m1,
                      torch::Tensor const& cv_ratio_m1,
                      torch::Tensor const& u0) {
  int grain_size = iter.numel() / at::get_num_threads();

  AT_DISPATCH_FLOATING_TYPES(iter.dtype(), "riemann_cpu", [&] {
    auto nhydro = at::native::ensure_nonempty_size(iter.output(0), 0);
    auto stride = at::native::ensure_nonempty_stride(iter.output(0), 0);
    bool moist = params.ideal_moist;
    RiemannArgs<scalar_t> a{
        dim,
        static_cast<int>(nhydro - ICY),
        static_cast<int>(stride),
        iter.ninputs() == 6,
        moist,
        params.nvapor,
        scalar_t(params.gammad),
        moist ? inv_mu_ratio_m1.data_ptr<scalar_t>() : nullptr,
        moist ? cv_ratio_m1.data_ptr<scalar_t>() : nullptr,
        moist ? u0.data_ptr<scalar_t>() : nullptr,
        params.dir_yz};
    int nt = iter.ntensors();

    iter.for_each(
        [&](char** data, const int64_t* strides, int64_t n) {
          scalar_t* p[(C ? 9 : 8) + (E ? 1 : 0) + (W ? 1 : 0)];
          for (int64_t i = 0; i < n; ++i) {
            for (int k = 0; k < nt; ++k)
              p[k] = reinterpret_cast<scalar_t*>(data[k] + i * strides[k]);
            riemann_face<K, C, E, W>(p, a);
          }
        },
        grain_size);
  });
}

// the runtime flags to template arguments: C, W for every kind, E for roe
template <RiemannKind K, bool E, bool C>
void riemann_cpu_w(bool w, at::TensorIterator& iter, int dim,
                   RiemannParams const& params, torch::Tensor const& t1,
                   torch::Tensor const& t2, torch::Tensor const& t3) {
  if (w) return riemann_cpu_loop<K, C, E, true>(iter, dim, params, t1, t2, t3);
  riemann_cpu_loop<K, C, E, false>(iter, dim, params, t1, t2, t3);
}

template <RiemannKind K, bool E>
void riemann_cpu_cw(RiemannParams const& params, at::TensorIterator& iter,
                    int dim, torch::Tensor const& t1, torch::Tensor const& t2,
                    torch::Tensor const& t3) {
  if (params.central)
    return riemann_cpu_w<K, E, true>(params.speed, iter, dim, params, t1, t2,
                                     t3);
  riemann_cpu_w<K, E, false>(params.speed, iter, dim, params, t1, t2, t3);
}

}  // namespace

void riemann_cpu(at::TensorIterator& iter, int kind, int dim,
                 RiemannParams const& params,
                 torch::Tensor const& inv_mu_ratio_m1,
                 torch::Tensor const& cv_ratio_m1, torch::Tensor const& u0) {
  auto const& t1 = inv_mu_ratio_m1;
  auto const& t2 = cv_ratio_m1;
  auto const& t3 = u0;
  switch (static_cast<RiemannKind>(kind)) {
    case RiemannKind::hllc:
      return riemann_cpu_cw<RiemannKind::hllc, false>(params, iter, dim, t1, t2,
                                                      t3);
    case RiemannKind::lmars:
      return riemann_cpu_cw<RiemannKind::lmars, false>(params, iter, dim, t1,
                                                       t2, t3);
    case RiemannKind::roe:
      if (params.llf)
        return riemann_cpu_cw<RiemannKind::roe, true>(params, iter, dim, t1, t2,
                                                      t3);
      return riemann_cpu_cw<RiemannKind::roe, false>(params, iter, dim, t1, t2,
                                                     t3);
    case RiemannKind::shallow_roe:
      return riemann_cpu_cw<RiemannKind::shallow_roe, false>(params, iter, dim,
                                                             t1, t2, t3);
    default:
      TORCH_CHECK(false, "[call_riemann] kind ", kind,
                  " is a torch formula, not a face function");
  }
}

}  // namespace snap

namespace at::native {

DEFINE_DISPATCH(call_riemann);
REGISTER_ALL_CPU_DISPATCH(call_riemann, &snap::riemann_cpu);
REGISTER_MPS_DISPATCH(call_riemann, &snap::OnHost<&snap::riemann_cpu>::run);

}  // namespace at::native
