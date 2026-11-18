// Gate probe for V3 C2 (tools/gate_c2): each kernel that C2 registers for
// MPS, OnHost<cpu kernel>, runs on CUDA tensors (a device that is not the
// host, as MPS is) against the same CPU kernel on CPU tensors. Pass: every
// case torch::equal, and no compared output is all zero. Needs a CUDA GPU;
// links the CPU build of the tree under test (CUDA=OFF is enough).
#include <ATen/TensorIterator.h>
#include <torch/torch.h>

#include <snap/snap.h>
#include <snap/hydro/hydro_dispatch.hpp>
#include <snap/hydro/hydro_reference.hpp>
#include <snap/recon/interpolation.hpp>
#include <snap/utils/on_host.hpp>

#include <cstdio>
#include <string>
#include <vector>

namespace snap {
template <int N>
void call_poly_cpu(at::TensorIterator& iter, torch::Tensor coeff, int dim);
void call_weno3_cpu(at::TensorIterator&, torch::Tensor, int, bool);
void call_weno5_cpu(at::TensorIterator&, torch::Tensor, int, bool);
void call_hllc_cpu(at::TensorIterator&, int);
void call_lmars_cpu(at::TensorIterator&, int);
void call_roe_cpu(at::TensorIterator&, int, bool, int, double,
                  torch::Tensor const&, torch::Tensor const&,
                  torch::Tensor const&);
void call_shallow_roe_cpu(at::TensorIterator&, int, int);
void hydro_pressure_scan_x1_cpu(torch::Tensor const&, torch::Tensor const&,
                                torch::Tensor const&, torch::Tensor const&,
                                torch::Tensor const&, int, double);
void hydro_ref_x1_cpu(torch::Tensor const&, torch::Tensor const&,
                      torch::Tensor const&, torch::Tensor const&,
                      torch::Tensor const&, torch::Tensor const&,
                      torch::Tensor const&, torch::Tensor const&, int, double,
                      int, bool, bool, bool, torch::Tensor const&);
}  // namespace snap

using namespace snap;
static int fails = 0, checks = 0;
static void check(char const* what, torch::Tensor a, torch::Tensor b) {
  ++checks;
  bool eq = torch::equal(a.cpu(), b.cpu());
  bool zero = a.abs().max().item<double>() == 0.;
  if (!eq || zero) ++fails;
  std::printf("%-44s %s  max|out|=%.3e\n", what,
              !eq ? "DIFFERENT" : zero ? "ALL ZERO" : "bitwise equal",
              a.abs().max().item<double>());
}

// MPS-style iterator (squash only dim 0, as x1_uniform_iterator does off CUDA)
static at::TensorIterator recon_iter(torch::Tensor const& w,
                                     torch::Tensor const& out) {
  return at::TensorIteratorConfig()
      .resize_outputs(false)
      .check_all_same_dtype(true)
      .declare_static_shape(out.sizes(), {0})
      .add_output(out)
      .add_input(w)
      .build();
}

template <typename Run>
static void recon_case(char const* name, torch::Tensor coeff, int st,
                       torch::Dtype dt, Run run) {
  torch::manual_seed(1);
  auto w = (1. + 0.1 * torch::rand({5, 1, 12, 20}, torch::kFloat64)).to(dt);
  w[2] *= 1.e-10;
  for (int dim : {2, 3}) {
    auto vec = w.sizes().vec();
    vec[dim] -= st - 1;
    auto oc = torch::empty(vec, w.options());
    auto og = torch::empty(vec, w.options().device(torch::kCUDA));
    auto ic = recon_iter(w, oc);
    auto wg = w.cuda();  // named: the iterator borrows it
    auto ig = recon_iter(wg, og);
    run(ic, coeff.to(dt), dim, false);
    run(ig, coeff.to(dt).cuda(), dim, true);
    char buf[96];
    std::snprintf(buf, sizeof(buf), "%s dim=%d %s", name, dim,
                  dt == torch::kFloat32 ? "f32" : "f64");
    check(buf, oc, og);
  }
}

// the iterator borrows its operands: callers keep every tensor alive
static at::TensorIterator riemann_iter(torch::Tensor const& flx,
                                       torch::Tensor const& fp,
                                       std::vector<torch::Tensor> const& in) {
  at::TensorIteratorConfig c;
  c.resize_outputs(false).declare_static_shape(flx.sizes(), 0).add_output(flx);
  if (fp.defined()) c.add_owned_output(fp.unsqueeze(0));
  for (auto& t : in) c.add_input(t);
  return c.build();
}

int main() {
  auto cuda = torch::kCUDA;
  for (auto dt : {torch::kFloat32, torch::kFloat64}) {
    // reconstruction: one CPU loop per scheme (call_poly3/5, call_weno3/5)
    auto mk = [](char const* t, bool scale) {
      auto o = InterpOptionsImpl::create();
      o->type() = t;
      o->scale() = scale;
      return o;
    };
    for (bool scale : {false, true}) {
      Weno5InterpImpl w5(mk("weno5", scale));
      recon_case(scale ? "weno5 scale" : "weno5", w5.cm, 5, dt,
                 [&](at::TensorIterator& it, torch::Tensor c, int d, bool g) {
                   g ? OnHost<&call_weno5_cpu>::run(it, c, d, scale)
                     : call_weno5_cpu(it, c, d, scale);
                 });
      Weno3InterpImpl w3(mk("weno3", scale));
      recon_case(scale ? "weno3 scale" : "weno3", w3.cm, 3, dt,
                 [&](at::TensorIterator& it, torch::Tensor c, int d, bool g) {
                   g ? OnHost<&call_weno3_cpu>::run(it, c, d, scale)
                     : call_weno3_cpu(it, c, d, scale);
                 });
    }
    Center5InterpImpl c5(mk("cp5", false));
    recon_case("cp5 (poly5)", c5.cm, 5, dt,
               [&](at::TensorIterator& it, torch::Tensor c, int d, bool g) {
                 g ? OnHost<&call_poly_cpu<5>>::run(it, c, d)
                   : call_poly_cpu<5>(it, c, d);
               });
    Center3InterpImpl c3(mk("cp3", false));
    recon_case("cp3 (poly3)", c3.cm, 3, dt,
               [&](at::TensorIterator& it, torch::Tensor c, int d, bool g) {
                 g ? OnHost<&call_poly_cpu<3>>::run(it, c, d)
                   : call_poly_cpu<3>(it, c, d);
               });

    // Riemann: ideal gas left/right states, 5 variables
    torch::manual_seed(2);
    auto o = torch::TensorOptions().dtype(dt);
    auto wl = torch::rand({5, 1, 4, 8}, o) + 0.5, wr = torch::rand_like(wl) + 0.5;
    wl.narrow(0, 1, 3) -= 1.;
    wr.narrow(0, 1, 3) -= 1.;
    double g = 1.4;
    auto elr = torch::stack({wl[4] / (g - 1), wr[4] / (g - 1)});
    auto glr = torch::full_like(elr, g);
    auto clr = torch::stack({(g * wl[4] / wl[0]).sqrt(), (g * wr[4] / wr[0]).sqrt()});
    for (int dim : {3, 2}) {
      char buf[96];
      std::snprintf(buf, sizeof(buf), "dim=%d %s", dim,
                    dt == torch::kFloat32 ? "f32" : "f64");
      {
        auto fc = torch::zeros_like(wl), pc = torch::zeros_like(wl[0]);
        auto fg = fc.cuda(), pg = pc.cuda();
        std::vector<torch::Tensor> ac{wl, wr, elr, glr, clr},
            ag{wl.cuda(), wr.cuda(), elr.cuda(), glr.cuda(), clr.cuda()};
        auto ic = riemann_iter(fc, pc, ac);
        auto ig = riemann_iter(fg, pg, ag);
        call_hllc_cpu(ic, dim);
        OnHost<&call_hllc_cpu>::run(ig, dim);
        check((std::string("hllc flux ") + buf).c_str(), fc, fg);
        check((std::string("hllc face pressure ") + buf).c_str(), pc, pg);
      }
      {
        auto fc = torch::zeros_like(wl), pc = torch::zeros_like(wl[0]);
        auto fg = fc.cuda(), pg = pc.cuda();
        std::vector<torch::Tensor> ac{wl, wr, elr, glr},
            ag{wl.cuda(), wr.cuda(), elr.cuda(), glr.cuda()};
        auto ic = riemann_iter(fc, pc, ac);
        auto ig = riemann_iter(fg, pg, ag);
        call_lmars_cpu(ic, dim);
        OnHost<&call_lmars_cpu>::run(ig, dim);
        check((std::string("lmars flux ") + buf).c_str(), fc, fg);
        check((std::string("lmars face pressure ") + buf).c_str(), pc, pg);
      }
      {
        auto fc = torch::zeros_like(wl), pc = torch::zeros_like(wl[0]);
        auto fg = fc.cuda(), pg = pc.cuda();
        std::vector<torch::Tensor> ac{wl, wr, elr, glr, clr},
            ag{wl.cuda(), wr.cuda(), elr.cuda(), glr.cuda(), clr.cuda()};
        auto ic = riemann_iter(fc, pc, ac);
        auto ig = riemann_iter(fg, pg, ag);
        torch::Tensor none;
        call_roe_cpu(ic, dim, false, 0, g, none, none, none);
        OnHost<&call_roe_cpu>::run(ig, dim, false, 0, g, none, none, none);
        check((std::string("roe flux ") + buf).c_str(), fc, fg);
        check((std::string("roe face pressure ") + buf).c_str(), pc, pg);
      }
      {
        auto hl = wl.narrow(0, 0, 4).clone(), hr = wr.narrow(0, 0, 4).clone();
        auto fc = torch::zeros_like(hl), fg = fc.cuda();
        torch::Tensor none;
        std::vector<torch::Tensor> ac{hl, hr}, ag{hl.cuda(), hr.cuda()};
        auto ic = riemann_iter(fc, none, ac);
        auto ig = riemann_iter(fg, none, ag);
        call_shallow_roe_cpu(ic, dim, 0);
        OnHost<&call_shallow_roe_cpu>::run(ig, dim, 0);
        check((std::string("shallow-roe flux ") + buf).c_str(), fc, fg);
      }
    }

    // x1 reference: pressure scan and the full reference (uniform x1)
    auto rho = (torch::arange(60, o).reshape({2, 3, 10}) - 31.) * 1.e-7 + 1.;
    auto dx = torch::linspace(.1, .4, 10, o);
    auto anchor = (torch::arange(6, o).reshape({2, 3, 1}) + 3.) * 1.e3;
    for (int iu : {0, 7, 9}) {
      auto lc = torch::empty_like(rho), hc = torch::empty_like(rho);
      auto lg = lc.cuda(), hg = hc.cuda();
      hydro_pressure_scan_x1_cpu(rho, dx, anchor, lc, hc, iu, -9.8);
      OnHost<&hydro_pressure_scan_x1_cpu>::run(rho.cuda(), dx.cuda(),
                                               anchor.cuda(), lg, hg, iu, -9.8);
      char buf[96];
      std::snprintf(buf, sizeof(buf), "pressure scan iu=%d %s", iu,
                    dt == torch::kFloat32 ? "f32" : "f64");
      check(buf, torch::cat({lc, hc}), torch::cat({lg, hg}));
    }
    auto w = torch::zeros({5, 2, 3, 16}, o);
    auto z = torch::arange(16, o) * 100.;
    w[0] = 1.2 * torch::exp(-z / 8000.);
    w[4] = 1.e5 * torch::exp(-z / 8000.);
    auto dxu = torch::full({16}, 100., o);
    for (bool walls : {false, true}) {
      HydroReferenceX1 c(w), d(w.cuda());
      hydro_ref_x1_cpu(w, dxu, {}, c.psf_lo, c.psf_hi, c.pref, c.dsf, c.dref,
                       12, -9.8, kX1RefUniform, walls, walls, walls, {});
      OnHost<&hydro_ref_x1_cpu>::run(w.cuda(), dxu.cuda(), {}, d.psf_lo,
                                     d.psf_hi, d.pref, d.dsf, d.dref, 12, -9.8,
                                     kX1RefUniform, walls, walls, walls, {});
      char buf[96];
      std::snprintf(buf, sizeof(buf), "x1 reference uniform walls=%d %s",
                    int(walls), dt == torch::kFloat32 ? "f32" : "f64");
      check(buf, torch::cat({c.psf_lo, c.psf_hi, c.pref, c.dsf, c.dref}),
            torch::cat({d.psf_lo, d.psf_hi, d.pref, d.dsf, d.dref}));
    }
  }
  std::printf("TOTAL %d/%d bitwise equal\n", checks - fails, checks);
  return fails ? 1 : 0;
}
