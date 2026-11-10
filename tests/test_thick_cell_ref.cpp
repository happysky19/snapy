// The x1 top face on a hydrostatic column, and the guard for a column deep
// enough to reach the configured density floor. happysky19/snapy#5.
// Both assertions are RED at the parent of this commit.
#include <gtest/gtest.h>
#include <snap/snap.h>
#include <unistd.h>

#include <cmath>
#include <fstream>
#include <iomanip>
#include <snap/hydro/balance_column.hpp>
#include <snap/hydro/hydro_dispatch.hpp>
#include <snap/mesh/meshblock.hpp>
#include <string>
#include <vector>

#include "cuda_test_gate.hpp"

namespace {
constexpr double kGrav = 10.44, kRd = 3777., kT0 = 300., kPs = 1.e5;
constexpr int kN = 42;
constexpr double kA = 0.5;  // dz/H; this column is 21 scale heights deep

//! an isothermal column `n` cells deep, each `a` scale heights thick
torch::Tensor column(double a, int n, torch::TensorOptions const& opt) {
  auto p = kPs * torch::exp(-(torch::arange(n, opt) + 0.5) * a);
  auto w = torch::zeros({snap::IPR + 1, 1, 1, n}, opt);
  w[snap::IPR].copy_(p.view({1, 1, n}));
  w[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, n}));
  return w;
}

//! that column's deck, with the density floor set to rho_top / `ratio`
snap::MeshBlock block_at_floor_ratio(double ratio, double a = kA, int n = kN) {
  double dz = a * kRd * kT0 / kGrav;
  double rho_top = kPs * std::exp(-(n - 0.5) * a) / (kRd * kT0);
  char f[] = "/tmp/thickcell-XXXXXX";
  int fd = mkstemp(f);
  if (fd != -1) close(fd);
  std::ofstream(f)
      << std::setprecision(17) << "reference-state: {Tref: 0., Pref: 1.e5}\n"
      << "species: [{name: dry, composition: {H: 2}, cv_R: 2.5}]\n"
      << "geometry: {type: cartesian, bounds: {x1min: 0., x1max: " << dz * n
      << ", x2min: 0., x2max: 1., x3min: 0., x3max: 1.}, cells: {nx1: " << n
      << ", nx2: 1, nx3: 1, nghost: 3}}\ndynamics:\n"
      << "  equation-of-state: {type: ideal-gas, gammad: 1.4, weight: "
      << 8.31446261815324 / kRd << ", density-floor: " << rho_top / ratio
      << ", pressure-floor: 1.e-30, limiter: true}\n"
      << "  reconstruct: {vertical: {type: weno5, scale: false, shock: false},"
      << " horizontal: {type: weno5, scale: false, shock: false}}\n"
      << "  riemann-solver: {type: lmars}\n"
      << "boundary-condition: {external: {x1-inner: reflecting, x1-outer: "
      << "reflecting}}\nintegration: {type: rk3, cfl: 0.4}\n"
      << "forcing: {const-gravity: {grav1: -" << kGrav << "}}\n";
  auto blk = snap::MeshBlock(snap::MeshBlockOptionsImpl::from_yaml(f));
  std::remove(f);
  blk->to(torch::kCPU, torch::kFloat64);
  return blk;
}
}  // namespace

//! The scan invents the face above the top cell, and every cell reference
//! reads w[IPR] as a cell AVERAGE, so the log-mean of the top cell's own two
//! faces must be its stored pressure. RED at the parent, whose half-cell
//! extrapolation is the face above a POINT value at the cell centre: it
//! misses by 4.3130e-03 relative at dz/H = 0.35 and 1.2345e-01 at 3.0.
TEST(ThickCellRef, top_face_is_average_consistent) {
  for (auto dev : {torch::kCPU, torch::kCUDA}) {
    if (dev == torch::kCUDA && !snapy_cuda_test_enabled()) continue;
    auto opt = torch::TensorOptions().dtype(torch::kFloat64).device(dev);
    for (double a : {0.1, 0.35, 0.75, 1.5, 3.0}) {
      const int n = 8;
      std::vector<int64_t> sz{1, 1, n};
      auto lo = torch::empty(sz, opt), hi = torch::empty(sz, opt);
      auto pref = torch::empty(sz, opt), dsf = torch::empty(sz, opt);
      auto dref = torch::empty(sz, opt);
      torch::Tensor anchor, rows;
      at::native::call_hydro_ref_x1(
          dev, column(a, n, opt), torch::full({n}, a * kRd * kT0 / kGrav, opt),
          anchor, lo, hi, pref, dsf, dref, n - 1, kGrav, snap::kX1RefUniform,
          true, true, true, rows);
      double l = lo.flatten()[n - 1].item<double>();
      double h = hi.flatten()[n - 1].item<double>();
      double p_top = kPs * std::exp(-(n - 0.5) * a);
      EXPECT_NEAR((l - h) / std::log(l / h), p_top, 1.e-12 * p_top)
          << "a=" << a << " dev=" << static_cast<int>(dev);
    }
  }
}

//! A column whose top cell starts at or below the configured density floor
//! fails MeshBlockImpl::floor_hit, min(rho) > 1.001 * density_floor, on its
//! first step and on every redo after, so the run dies by exhausting its redo
//! budget with a dt-halving message that names no cause. Refuse it at setup
//! on that same factor.
//!
//! The factor is the solver's, not a chosen margin, and the two agree at
//! every sampled point. Measured on this column with the guard disabled, so
//! the stepping answer does not depend on it: ratios 0.9990, 1.0000, 1.0005,
//! 1.0009 and 1.0010 all terminate, each at step 6 when the redo budget runs
//! out; 1.0011 is the first that holds, at |v|/cs = 4.659e-11 over 100 steps,
//! and every larger ratio gives that same figure. Nominal 1.0010 is refused
//! because it lands at 1.0009999999999999 in double precision. The ratios
//! below stay clear of that boundary on purpose. 27.96 is this
//! investigation's realistic hot H2 column.
//! RED at the parent: every ratio initializes without complaint.
TEST(ThickCellRef, the_density_floor_guard_refuses_only_unsteppable_columns) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  for (double ratio : {0.5, 0.9, 1.0, 1.002, 2.0, 27.96}) {
    auto blk = block_at_floor_ratio(ratio);
    auto co = blk->pcoord->options;
    auto w =
        torch::zeros({snap::IPR + 1, co->nc3(), co->nc2(), co->nc1()}, opt);
    w.narrow(-1, blk->pcoord->il(), kN).copy_(column(kA, kN, opt));
    snap::Variables v{{"hydro_w", w}};
    if (ratio > 1.001) {
      EXPECT_NO_THROW(blk->initialize(v)) << "ratio " << ratio;
    } else {
      EXPECT_THROW(blk->initialize(v), c10::Error) << "ratio " << ratio;
    }
  }
}

//! A reference the six-face rows cannot hold positive is refused when it is
//! first built, naming the cell and its dz/H. The factored rows hold the
//! five-cell isothermal column at 1.25 H (whose restored top face was -29.07
//! Pa with the p rows), so the refusal is exercised on a column they cannot
//! hold: dz = 1.5 bottom scale heights and T falling linearly from 300 K to
//! 60 K, which leaves the top cell 7.5 of its own scale heights thick and its
//! restored top face p_top - pref_top + psf_top at -3.4 p_top. The isothermal
//! 1.0 H column runs. RED at the parent: both run.
TEST(ThickCellRef, a_non_positive_reference_is_refused_at_its_first_build) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  for (double ttop : {kT0, 60.}) {
    double a = ttop < kT0 ? 1.5 : 1.0;
    auto blk = block_at_floor_ratio(1.e6, a, 5);
    auto co = blk->pcoord->options;
    auto w =
        torch::zeros({snap::IPR + 1, co->nc3(), co->nc2(), co->nc1()}, opt);
    auto col = column(a, 5, opt);
    if (ttop < kT0) {  // T linear in the cell index, p by the cell-to-cell drop
      double dz = a * kRd * kT0 / kGrav;
      auto p = col[snap::IPR].flatten(), rho = col[snap::IDN].flatten();
      double pi = kPs, tprev = kT0;
      for (int i = 0; i < 5; ++i) {
        double t = kT0 + (ttop - kT0) * i / 4.;
        if (i > 0) pi *= std::exp(-kGrav * dz / (kRd * 0.5 * (t + tprev)));
        p[i] = pi;
        rho[i] = pi / (kRd * t);
        tprev = t;
      }
    }
    w.narrow(-1, blk->pcoord->il(), 5).copy_(col);
    snap::Variables v{{"hydro_w", w}};
    blk->initialize(v);
    if (ttop == kT0) {
      EXPECT_NO_THROW(blk->forward(v, 1.e-3, 0)) << "dz/H " << a;
    } else {
      try {
        blk->forward(v, 1.e-3, 0);
        ADD_FAILURE() << "a cold top 7.5 scale heights thick was accepted";
      } catch (c10::Error const& e) {
        std::string m = e.what_without_backtrace();
        EXPECT_NE(m.find("restored top-face pressure"), std::string::npos) << m;
        EXPECT_NE(m.find("owned x1 cell 4"), std::string::npos) << m;
      }
    }
  }
}

//! and balance_column's refusal names its worst cell and dz/H: a sweep
//! budget of one cannot balance the marched 1.25 H column
TEST(ThickCellRef, an_unbalanced_column_is_refused_with_its_cell_and_dz_h) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  auto col = column(1.25, 5, opt);
  col[snap::IPR].mul_(1. + 0.01 * torch::arange(5, opt).view({1, 1, 5}));
  auto dx1f = torch::full({5}, 1.25 * kRd * kT0 / kGrav, opt);
  try {
    snap::balance_column(col, dx1f, kGrav, true, 1.e-13, 1, "cartesian");
    ADD_FAILURE() << "one sweep balanced a perturbed column";
  } catch (c10::Error const& e) {
    std::string m = e.what_without_backtrace();
    EXPECT_NE(m.find("largest at x1 cell"), std::string::npos) << m;
    EXPECT_NE(m.find("dz/H = "), std::string::npos) << m;
  }
}
