// torch
#include <ATen/Dispatch.h>
#include <ATen/TensorIterator.h>
#include <ATen/native/ReduceOpsUtils.h>
#include <c10/cuda/CUDAGuard.h>

// snap
#include <snap/utils/loops.cuh>

#include "riemann_dispatch.hpp"
#include "riemann_kernels.h"

namespace snap {

// One CUDA loop for every face-function kind: N0 operands plus the optional
// outputs, each face is riemann_face<K, C, E, W>, C when the iterator carries
// riemann.central, E when it carries roe's LLF flag, W when it carries the
// wave speed.
template <RiemannKind K, int N0, bool C, bool E, bool W>
void riemann_cuda_loop(at::TensorIterator &iter, int dim,
                       RiemannParams const &params,
                       torch::Tensor const &inv_mu_ratio_m1,
                       torch::Tensor const &cv_ratio_m1,
                       torch::Tensor const &u0) {
  constexpr int N = N0 + (C ? 1 : 0) + (E ? 1 : 0) + (W ? 1 : 0);
  AT_DISPATCH_FLOATING_TYPES(iter.common_dtype(), "riemann_cuda", [&]() {
    auto nhydro = at::native::ensure_nonempty_size(iter.output(0), 0);
    auto stride = at::native::ensure_nonempty_stride(iter.output(0), 0);
    bool moist = params.ideal_moist;
    RiemannArgs<scalar_t> a{
        dim,
        static_cast<int>(nhydro - ICY),
        static_cast<int>(stride),
        N0 == 8,
        moist,
        params.nvapor,
        scalar_t(params.gammad),
        moist ? inv_mu_ratio_m1.data_ptr<scalar_t>() : nullptr,
        moist ? cv_ratio_m1.data_ptr<scalar_t>() : nullptr,
        moist ? u0.data_ptr<scalar_t>() : nullptr,
        params.dir_yz};

    native::gpu_kernel<N>(
        iter, [=] GPU_LAMBDA(char *const data[N], unsigned int strides[N]) {
          scalar_t *p[(C ? 9 : 8) + (E ? 1 : 0) + (W ? 1 : 0)];
#pragma unroll
          for (int k = 0; k < N; ++k)
            p[k] = reinterpret_cast<scalar_t *>(data[k] + strides[k]);
          riemann_face<K, C, E, W>(p, a);
        });
  });
}

// the runtime flags to template arguments: C, W for every kind, E for roe
template <RiemannKind K, int N0, bool E, bool C>
void riemann_cuda_w(RiemannParams const &params, at::TensorIterator &iter,
                    int dim, torch::Tensor const &t1, torch::Tensor const &t2,
                    torch::Tensor const &t3) {
  if (params.speed)
    return riemann_cuda_loop<K, N0, C, E, true>(iter, dim, params, t1, t2, t3);
  riemann_cuda_loop<K, N0, C, E, false>(iter, dim, params, t1, t2, t3);
}

template <RiemannKind K, int N0, bool E>
void riemann_cuda_cw(RiemannParams const &params, at::TensorIterator &iter,
                     int dim, torch::Tensor const &t1, torch::Tensor const &t2,
                     torch::Tensor const &t3) {
  if (params.central)
    return riemann_cuda_w<K, N0, E, true>(params, iter, dim, t1, t2, t3);
  riemann_cuda_w<K, N0, E, false>(params, iter, dim, t1, t2, t3);
}

void riemann_cuda(at::TensorIterator &iter, int kind, int dim,
                  RiemannParams const &params,
                  torch::Tensor const &inv_mu_ratio_m1,
                  torch::Tensor const &cv_ratio_m1, torch::Tensor const &u0) {
  at::cuda::CUDAGuard device_guard(iter.device());
  auto const &t1 = inv_mu_ratio_m1;
  auto const &t2 = cv_ratio_m1;
  auto const &t3 = u0;
  switch (static_cast<RiemannKind>(kind)) {
    case RiemannKind::hllc:
      // seven base operands, eight with the face background p0
      if (iter.ninputs() == 6)
        return riemann_cuda_cw<RiemannKind::hllc, 8, false>(params, iter, dim,
                                                            t1, t2, t3);
      return riemann_cuda_cw<RiemannKind::hllc, 7, false>(params, iter, dim, t1,
                                                          t2, t3);
    case RiemannKind::lmars:
      return riemann_cuda_cw<RiemannKind::lmars, 6, false>(params, iter, dim,
                                                           t1, t2, t3);
    case RiemannKind::roe:
      if (params.llf)
        return riemann_cuda_cw<RiemannKind::roe, 7, true>(params, iter, dim, t1,
                                                          t2, t3);
      return riemann_cuda_cw<RiemannKind::roe, 7, false>(params, iter, dim, t1,
                                                         t2, t3);
    case RiemannKind::shallow_roe:
      return riemann_cuda_cw<RiemannKind::shallow_roe, 3, false>(
          params, iter, dim, t1, t2, t3);
    default:
      TORCH_CHECK(false, "[call_riemann] kind ", kind,
                  " is a torch formula, not a face function");
  }
}

}  // namespace snap

namespace at::native {

REGISTER_CUDA_DISPATCH(call_riemann, &snap::riemann_cuda);

}  // namespace at::native
