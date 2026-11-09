// Cells thick against the pressure scale height, a = dz/H = g rho dz / p,
// which nothing in the tree ran above ~1. Measurements: happysky19/snapy#5.
#include <gtest/gtest.h>
#include <snap/snap.h>
#include <torch/torch.h>

#include <cstdio>
#include <cstdlib>  // mkstemp
#include <snap/hydro/balance_column.hpp>
#include <snap/mesh/meshblock.hpp>
#include <string>
#include <tuple>

#include "cuda_test_gate.hpp"
namespace {
constexpr double kGrav = 10.44, kRd = 3777., kGamma = 1.4, kT0 = 300.,
                 kPs = 1.e5, kH = kRd * kT0 / kGrav;
constexpr int kNx1 = 5, kNg = 3, kSteps = 300;
constexpr char kDeck[] =  // full precision: at 6 digits dx1f differs in the 7th
    R"(species: [{name: dry, composition: {H: 2}, cv_R: 2.5}]
geometry: {type: cartesian, cells: {nx1: %d, nx2: 1, nx3: 1, nghost: %d}, bounds: {x1min: 0., x1max: %.17g, x2min: 0., x2max: 1., x3min: 0., x3max: 1.}}
dynamics: {equation-of-state: {type: ideal-gas, gammad: %.17g, weight: %.17g, density-floor: 1.e-30, pressure-floor: 1.e-30, limiter: false}, reconstruct: {vertical: {type: weno5, scale: false, shock: false}}, riemann-solver: {type: lmars}}
boundary-condition: {external: {x1-inner: reflecting, x1-outer: reflecting}}
integration: {type: rk3, cfl: 0.4, implicit-scheme: %d}
forcing: {const-gravity: {grav1: %.17g}})";
std::tuple<torch::Tensor, double, int> project(double a, torch::Tensor w = {}) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  if (!w.defined()) {
    auto p = kPs * torch::exp(-(torch::arange(kNx1, opt) + 0.5) * a);
    w = torch::zeros({snap::IPR + 1, 1, 1, kNx1}, opt);
    w[snap::IPR].copy_(p.view({1, 1, kNx1}));
    w[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, kNx1}));
  }
  return snap::balance_column(w, torch::full({kNx1}, a * kH, opt), kGrav, true,
                              1.e-13, 5000, "cartesian", false);
}
double drift(torch::Tensor const& col, double a, int imp,
             torch::DeviceType dev = torch::kCPU) {
  char y[1024], f[] = "/tmp/test-thick-cell-XXXXXX";
  std::snprintf(y, sizeof y, kDeck, kNx1, kNg, a * kH * kNx1, kGamma,
                8.31446261815324 / kRd, imp, -kGrav);
  std::FILE* fp = fdopen(mkstemp(f), "w");  // -1 on failure -> nullptr
  EXPECT_NE(fp, nullptr);
  if (fp) std::fputs(y, fp), std::fclose(fp);
  auto b = snap::MeshBlock(snap::MeshBlockOptionsImpl::from_yaml(f));
  std::remove(f);
  b->to(dev, torch::kFloat64);
  int il = b->pcoord->il();
  auto w = torch::zeros({col.size(0), 1, 1, b->pcoord->options->nc1()},
                        col.options().device(dev));
  w.narrow(-1, il, kNx1).copy_(col);  // the reflecting walls fill the ghosts
  snap::Variables v{{"hydro_w", w}};
  b->initialize(v);
  double mach = 0.;
  for (int n = 0; n < kSteps; ++n) {
    double dt = b->max_time_step(v);
    for (size_t s = 0; s < b->pintg->stages.size(); ++s) b->forward(v, dt, s);
    auto e = b->phydro->peos->compute("U->W", {v.at("hydro_u")})
                 .narrow(-1, il, kNx1);
    auto cs = (kGamma * e[snap::IPR] / e[snap::IDN]).sqrt();
    mach = std::max(mach, (e[snap::IVX].abs() / cs).max().item<double>());
  }
  return mach;
}
}  // namespace

// At fb003523 the a = 1.5 projection plateaus at 1.898760e-01 instead of
// converging; after the fix both reach the floor, are a fixed point, and rest,
// on the CPU and on the GPU (the gate and the limiter are device kernels too).
TEST(ThickCellRest, a_thick_isothermal_column_reaches_rest_and_keeps_it) {
  torch::set_num_threads(1);
  for (double a : {1.5, 3.0}) {
    auto [wb, err, sweeps] = project(a);
    EXPECT_LT(err, 1.e-13) << a;
    auto [wb2, err2, sweeps2] = project(a, wb);  // re-projection buys nothing
    auto rel = (wb2 - wb).abs() / wb.abs().clamp_min(1.e-300);  // v1 == 0
    EXPECT_LT(rel.max().item<double>(), 1.e-14) << a << " not a fixed point";
    std::printf("a=%.2f: residual %.6e in %d sweeps, re-projected %.6e in %d\n",
                a, err, sweeps, err2, sweeps2);
    for (int imp : {0, 1})
      for (auto dev : {torch::kCPU, torch::kCUDA})
        if (dev == torch::kCPU || snapy_cuda_test_enabled())
          EXPECT_LT(drift(wb, a, imp, dev), 1.e-12)
              << a << " scheme=" << imp << " dev=" << (int)dev;
  }
}

// Balancing is not being usable: by a = 4 the gauge drives a restored face
// pressure negative. fb003523 refuses a = 4 too, so the MESSAGE is asserted.
TEST(ThickCellRest, a_column_too_deep_for_one_gauge_is_refused) {
  try {
    project(4.0);
    ADD_FAILURE() << "a = 4 was certified";
  } catch (std::exception const& e) {
    EXPECT_NE(std::string(e.what()).find("restored face pressure"),
              std::string::npos)
        << e.what();
  }
}
