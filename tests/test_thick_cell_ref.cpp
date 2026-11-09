// The x1 reference on a thick hydrostatic column, and the floor guard that
// protects a column deep enough to reach the configured density floor.
// happysky19/snapy#5.
//
// Each test below is RED at the parent of this commit and GREEN with it; the
// measured values are in the comments.
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <limits>
#include <vector>

#include <unistd.h>

#include <gtest/gtest.h>

#include <snap/snap.h>
#include <snap/hydro/hydro_dispatch.hpp>
#include <snap/mesh/meshblock.hpp>

#include "cuda_test_gate.hpp"

namespace {
constexpr double kGrav = 10.44, kRd = 3777., kT0 = 300., kPs = 1.e5;

struct Ref {
  torch::Tensor psf_lo, psf_hi, pref;
};

//! the kernel's reference for an isothermal column of `n` cells, each `a`
//! scale heights thick, with no caller-supplied anchor
Ref reference(double a, int n, torch::DeviceType dev) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64).device(dev);
  double dz = a * kRd * kT0 / kGrav;
  auto dx1f = torch::full({n}, dz, opt);
  auto p = kPs * torch::exp(-(torch::arange(n, opt) + 0.5) * a);
  auto w = torch::zeros({snap::IPR + 1, 1, 1, n}, opt);
  w[snap::IPR].copy_(p.view({1, 1, n}));
  w[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, n}));

  std::vector<int64_t> sz{1, 1, n};
  Ref r{torch::empty(sz, opt), torch::empty(sz, opt), torch::empty(sz, opt)};
  auto dsf = torch::empty(sz, opt), dref = torch::empty(sz, opt);
  torch::Tensor anchor, rows;
  at::native::call_hydro_ref_x1(dev, w, dx1f, anchor, r.psf_lo, r.psf_hi,
                                r.pref, dsf, dref, n - 1, kGrav,
                                snap::kX1RefUniform, true, true, true, rows);
  return r;
}
}  // namespace

//! The top face has to be the one for which the top cell's own stored value
//! IS the average over that cell, because every cell reference below reads
//! w[IPR] as an average. The scan has no face above the top cell, so it
//! invents one; the half-cell extrapolation p exp(-thick/2) this replaced is
//! the face above a POINT value at the cell centre, and the two differ by
//! thick / (2 sinh(thick/2)).
//!
//! RED at the parent: the log-mean of the top cell's two faces misses its
//! stored pressure by 1.0e-02 relative at dz/H = 0.35 and 4.5e-01 at 3.0.
TEST(ThickCellRef, top_face_is_average_consistent) {
  for (auto dev : {torch::kCPU, torch::kCUDA}) {
    if (dev == torch::kCUDA && !snapy_cuda_test_enabled()) continue;
    for (double a : {0.1, 0.35, 0.75, 1.5, 3.0}) {
      const int n = 8;
      auto r = reference(a, n, dev);
      double lo = r.psf_lo.flatten()[n - 1].item<double>();
      double hi = r.psf_hi.flatten()[n - 1].item<double>();
      // the average of the log-linear profile through those two faces
      double logmean = (lo - hi) / std::log(lo / hi);
      double p_top = kPs * std::exp(-(n - 0.5) * a);
      EXPECT_NEAR(logmean, p_top, 1.e-12 * p_top)
          << "a=" << a << " dev=" << static_cast<int>(dev);
    }
  }
}

// The fallback that a rejected six-face row leaves behind is covered by
// tests/test_face_floor.cpp: its dipped column is the one deck in the suite
// where every row is rejected, so its mass flux measures the fallback
// directly, and that golden moved by 4.0% with this change. A standalone
// assertion here is not possible on a smooth isothermal column -- the cell
// bracket [hi, lo] widens as e^(dz/H), so the quadrature stays inside it and
// is accepted even at dz/H = 4, which was a wrong premise in an earlier
// draft of this file.

namespace {
//! a deck whose top cell sits at `ratio` times the configured density floor
snap::MeshBlock column_at_floor_ratio(double ratio) {
  const int n = 42;
  const double a = 0.5, dz = a * kRd * kT0 / kGrav;
  double rho_top = kPs * std::exp(-(n - 0.5) * a) / (kRd * kT0);
  char f[] = "/tmp/floorguard-XXXXXX";
  int fd = mkstemp(f);
  if (fd != -1) close(fd);
  std::ofstream o(f);
  o << std::setprecision(17)
    << "reference-state: {Tref: 0., Pref: 1.e5}\nspecies:\n  - name: dry\n"
    << "    composition: {H: 2}\n    cv_R: 2.5\ngeometry:\n  type: cartesian\n"
    << "  bounds: {x1min: 0., x1max: " << dz * n
    << ", x2min: 0., x2max: 1., x3min: 0., x3max: 1.}\n  cells: {nx1: " << n
    << ", nx2: 1, nx3: 1, nghost: 3}\ndynamics:\n"
    << "  equation-of-state: {type: ideal-gas, gammad: 1.4, weight: "
    << 8.31446261815324 / kRd << ", density-floor: " << rho_top / ratio
    << ", pressure-floor: 1.e-30, limiter: true}\n"
    << "  reconstruct:\n    vertical: {type: weno5, scale: false, shock: "
    << "false}\n    horizontal: {type: weno5, scale: false, shock: false}\n"
    << "  riemann-solver: {type: lmars}\nboundary-condition:\n"
    << "  external: {x1-inner: reflecting, x1-outer: reflecting}\n"
    << "integration: {type: rk3, cfl: 0.4}\nforcing:\n"
    << "  const-gravity: {grav1: -" << kGrav << "}\n";
  o.close();
  auto blk = snap::MeshBlock(snap::MeshBlockOptionsImpl::from_yaml(f));
  std::remove(f);
  blk->to(torch::kCPU, torch::kFloat64);
  return blk;
}

snap::Variables rest_state(snap::MeshBlock& blk) {
  const int n = 42;
  const double a = 0.5;
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  auto co = blk->pcoord->options;
  auto w = torch::zeros({snap::IPR + 1, co->nc3(), co->nc2(), co->nc1()}, opt);
  auto p = kPs * torch::exp(-(torch::arange(n, opt) + 0.5) * a);
  int il = blk->pcoord->il();
  w[snap::IPR].narrow(-1, il, n).copy_(p.view({1, 1, n}));
  w[snap::IDN].narrow(-1, il, n).copy_((p / (kRd * kT0)).view({1, 1, n}));
  return snap::Variables{{"hydro_w", w}};
}
}  // namespace

//! A column deep enough that its top cell starts at or below the configured
//! density floor can never take a step: check_redo's floor_hit fires on the
//! first one and on every redo after it, so the run dies by exhausting its
//! redo budget with a dt-halving message that says nothing about the cause.
//! Refuse it at setup instead, with the same 1.001 factor the step test uses
//! (src/mesh/meshblock.cpp:1302).
//!
//! The boundary is measured, not chosen: holding this column fixed and
//! varying only the configured floor, rho_top/floor = 1.0009 terminates on
//! step 1 and 1.0010 holds rest at |v|/cs = 4.66e-11 for 100 steps, with
//! every ratio from there to 100 giving the identical figure.
//!
//! RED at the parent: both ratios initialize without complaint.
TEST(ThickCellRef, a_column_under_the_density_floor_is_refused_at_setup) {
  for (double ratio : {0.5, 0.9, 1.0}) {
    auto blk = column_at_floor_ratio(ratio);
    auto v = rest_state(blk);
    EXPECT_THROW(blk->initialize(v), c10::Error) << "ratio " << ratio;
  }
}

//! and the complement: a ratio the solver can actually step is accepted.
//! 27.96 is the realistic hot H2 column of worker2/realcol-20261109.
TEST(ThickCellRef, a_column_clear_of_the_density_floor_is_accepted) {
  for (double ratio : {1.002, 2.0, 27.96, 1.e6}) {
    auto blk = column_at_floor_ratio(ratio);
    auto v = rest_state(blk);
    EXPECT_NO_THROW(blk->initialize(v)) << "ratio " << ratio;
  }
}
