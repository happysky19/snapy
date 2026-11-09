// A column whose CELLS are thick compared with the pressure scale height:
// a = dz/H = g rho dz / p, which nothing in the tree exercised above ~1
// (test_balance_column runs at 0.043). Measurements, and the 10,000-step runs
// this trims to 300 steps, are in happysky19/snapy#5.

#include <gtest/gtest.h>
#include <snap/snap.h>
#include <torch/torch.h>
#include <unistd.h>

#include <cstdio>
#include <snap/coord/coordinate.hpp>
#include <snap/hydro/balance_column.hpp>
#include <snap/mesh/meshblock.hpp>
#include <string>
#include <tuple>
#include <utility>

namespace {
constexpr double kGrav = 10.44, kRd = 3777., kGamma = 1.4, kT0 = 300.,
                 kPs = 1.e5, kH = kRd * kT0 / kGrav;
constexpr int kNx1 = 5, kNg = 3, kSteps = 300;

//! One column of kNx1 cells, walls at both ends, floats at full precision: at
//! 6 digits the block's dx1f differs from the column's in the 7th place.
constexpr char kDeck[] =
    R"(species: [{name: dry, composition: {H: 2}, cv_R: 2.5}]
geometry: {type: cartesian, cells: {nx1: %d, nx2: 1, nx3: 1, nghost: %d}, bounds: {x1min: 0., x1max: %.17g, x2min: 0., x2max: 1., x3min: 0., x3max: 1.}}
dynamics: {equation-of-state: {type: ideal-gas, gammad: %.17g, weight: %.17g, density-floor: 1.e-30, pressure-floor: 1.e-30, limiter: false}, reconstruct: {vertical: {type: weno5, scale: false, shock: false}}, riemann-solver: {type: lmars}}
boundary-condition: {external: {x1-inner: reflecting, x1-outer: reflecting}}
integration: {type: rk3, cfl: 0.4, implicit-scheme: %d}
forcing: {const-gravity: {grav1: %.17g}})";
constexpr char kGeom[] =
    R"(geometry: {type: cartesian, cells: {nx1: 16, nx2: 1, nx3: 1, nghost: %d, x1rat: %.17g}, bounds: {x1min: 0., x1max: 1.e6, x2min: 0., x2max: 1., x3min: 0., x3max: 1.}})";

std::string tmp_deck(char const* text) {
  char f[] = "/tmp/test-thick-cell-XXXXXX";
  int fd = mkstemp(f);
  EXPECT_NE(fd, -1);
  std::FILE* p = fdopen(fd, "w");
  std::fputs(text, p);
  std::fclose(p);
  return f;
}

//! the exact continuum column of `a` scale heights per cell, and its widths
std::pair<torch::Tensor, torch::Tensor> column(double a) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  auto p = kPs * torch::exp(-(torch::arange(kNx1, opt) + 0.5) * a);
  auto w = torch::zeros({snap::IPR + 1, 1, 1, kNx1}, opt);
  w[snap::IPR].copy_(p.view({1, 1, kNx1}));
  w[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, kNx1}));
  return {w, torch::full({kNx1}, a * kH, opt)};
}

//! max |v1| / c over every owned cell and every step, starting from `col`
double drift(torch::Tensor const& col, double dz, int imp) {
  char y[1024];
  std::snprintf(y, sizeof y, kDeck, kNx1, kNg, dz * kNx1, kGamma,
                8.31446261815324 / kRd, imp, -kGrav);
  auto f = tmp_deck(y);
  auto b = snap::MeshBlock(snap::MeshBlockOptionsImpl::from_yaml(f));
  std::remove(f.c_str());
  b->to(torch::kCPU, torch::kFloat64);
  int il = b->pcoord->il();
  auto co = b->pcoord->options;
  auto w = torch::zeros({col.size(0), co->nc3(), co->nc2(), co->nc1()},
                        col.options());
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

// At fb003523 the projection plateaus at 1.898760e-01 for a = 1.5 instead of
// converging, so the case stops there; after the fix both thicknesses reach
// their residual floor and hold rest in both paths.
TEST(ThickCellRest, a_thick_isothermal_column_reaches_rest_and_keeps_it) {
  torch::set_num_threads(1);
  for (double a : {1.5, 3.0}) {
    auto [w, dx1f] = column(a);
    torch::Tensor wb;
    double err = -1.;
    int sweeps = -1;
    ASSERT_NO_THROW(std::tie(wb, err, sweeps) = snap::balance_column(
                        w, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false))
        << "a=" << a;
    EXPECT_LT(err, 1.e-13) << "a=" << a;
    double ex = drift(wb, a * kH, 0), im = drift(wb, a * kH, 1);
    std::printf(
        "a=%.2f: residual %.6e in %d sweeps; max |w|/c over %d steps "
        "%.6e explicit, %.6e implicit\n",
        a, err, sweeps, kSteps, ex, im);
    EXPECT_LT(ex, 1.e-12) << "a=" << a << " explicit";
    EXPECT_LT(im, 1.e-12) << "a=" << a << " implicit";
  }
}

// Balancing is not being usable: by a = 4 the gauge drives a restored face
// pressure negative (residual 1.574e-16, face -5.240e-05) and the solver then
// exhausts its redos. That has to be an error, not a certified state.
TEST(ThickCellRest, a_column_too_deep_for_one_gauge_is_refused) {
  auto [w, dx1f] = column(4.0);
  EXPECT_THROW(snap::balance_column(w, dx1f, kGrav, true, 1.e-13, 5000,
                                    "cartesian", false),
               std::exception);
}

// cells/x1rat builds its faces from expm1, so adjacent width ratios come out
// as q (1 + O(eps)) and a STRICT test refused the documented bound itself.
TEST(ThickCellRest, the_x1rat_guard_admits_its_bound_and_refuses_more) {
  const double qmax = snap::CoordinateOptionsImpl::kX1MaxWidthRatio;
  for (double q : {qmax, 1.001 * qmax}) {
    char y[512];
    std::snprintf(y, sizeof y, kGeom, kNg, q);
    auto f = tmp_deck(y);
    if (q == qmax) {
      EXPECT_NO_THROW(snap::CoordinateOptionsImpl::from_yaml(f)) << "q=" << q;
    } else {
      EXPECT_THROW(snap::CoordinateOptionsImpl::from_yaml(f), std::exception);
    }
    std::remove(f.c_str());
  }
}
