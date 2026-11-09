// A column whose CELLS are thick compared with the pressure scale height.
//
// `a = dz/H = g rho dz / p` is a cell's hydrostatic thickness in scale
// heights. A deep atmosphere resolved coarsely in x1 -- a giant-planet
// interior, a radiative top -- reaches a ~ 1 and beyond, and nothing in the
// tree exercised that: tests/test_balance_column.cpp runs at a = 0.043 and
// tests/test_implicit_gravity_tall_column.py at a = 0.25.
//
// Across its six faces a hydrostatic column spans exp(5a) in pressure, while
// the cell's own bracket [psf_hi, psf_lo] is only exp(-a) of its lower face.
// So the degree-5 face quadrature's cancellation error, MEASURED AGAINST THE
// BRACKET THAT JUDGES IT, grows like exp(k a): the one-sided top-wall row
// leaves the bracket near a ~ 1.3, the centred row near a ~ 2.5. Two distinct
// failures follow, and the tests below are split along them:
//
//  * past the bracket the guard substitutes a mean of the two faces. The
//    ARITHMETIC mean is not a hydrostatically consistent cell average -- it
//    forces p_i/p_{i+1} = (2+a)/(2-a), which has no positive solution at all
//    for a >= 2 -- so the hybrid operator has no self-consistent rest state
//    and balance_column's iteration plateaus rather than converging.
//  * still INSIDE the bracket, around a ~ 1.25, the top row already
//    overestimates its cell enough that the gauge C = p' goes negative with
//    |C| above the top wall face pressure. The column then satisfies
//    p' == C to 1e-13 and is still unusable: the restored face pressure
//    C + psf_lo goes negative at the top wall, hydro_forward.cpp's positivity
//    fallback replaces it with bare psf_lo, and that finite jump lands exactly
//    where the well-balanced cancellation has to be exact.
//
// The log-mean (lo - hi)/ln(lo/hi) -- the exact average of the log-linear
// profile through the two faces, which kX1RefNonUniform already uses -- is
// strictly inside the bracket and satisfies p_i == pref_i identically for an
// isothermal column at ANY a. So the reference takes it once a cell is too
// thick for a polynomial quadrature of its faces.
//
// These check the two things a caller actually needs, not the branch taken:
// balance_column reaches a real fixed point, and the state it returns stays at
// rest in the solver -- in BOTH the explicit and the vertically implicit path,
// since they integrate the x1 momentum row differently.

// C/C++
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

// POSIX
#include <unistd.h>

// gtest
#include <gtest/gtest.h>

// torch
#include <torch/torch.h>

// snap
#include <snap/snap.h>

#include <snap/coord/coordinate.hpp>
#include <snap/hydro/balance_column.hpp>
#include <snap/hydro/hydro_dispatch.hpp>
#include <snap/mesh/meshblock.hpp>

namespace {

constexpr double kGrav = 10.44;  // Saturn-like g
constexpr double kRd = 3777.0;   // Jovian H2/He
constexpr double kGamma = 1.4;
constexpr double kT0 = 300.0;
constexpr double kPs = 1.0e5;
constexpr int kNg = 3;

//! H = Rd T / g, the isothermal pressure scale height [m]
double scale_height() { return kRd * kT0 / kGrav; }

//! A uniform ghost-free isothermal column of `nx1` cells, each `a` scale
//! heights thick, sampled from the EXACT continuum solution at cell centres.
//! Exact sampling matters: the defect under test is the reference operator's,
//! not a marching truncation, so the fixture must not carry one of its own.
std::pair<torch::Tensor, torch::Tensor> isothermal_column(int nx1, double a) {
  double dz = a * scale_height();
  auto opt = torch::TensorOptions().dtype(torch::kFloat64);
  auto dx1f = torch::full({nx1}, dz, opt);
  auto w = torch::zeros({snap::IPR + 1, 1, 1, nx1}, opt);
  auto zc = (torch::arange(nx1, opt) + 0.5) * dz;
  auto p = kPs * torch::exp(-zc / scale_height());
  w[snap::IPR].copy_(p.view({1, 1, nx1}));
  w[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, nx1}));
  return {w, dx1f};
}

struct Ref {
  torch::Tensor psf_lo, psf_hi, pref, dsf, dref;
};

//! The kernel's own reference for a ghost-free column, both x1 ends physical
//! and the wall clamp on -- exactly the call balance_column iterates against.
Ref reference(torch::Tensor const& w, torch::Tensor const& dx1f) {
  auto sizes = w.sizes().slice(1).vec();
  Ref r{torch::empty(sizes, w.options()), torch::empty(sizes, w.options()),
        torch::empty(sizes, w.options()), torch::empty(sizes, w.options()),
        torch::empty(sizes, w.options())};
  torch::Tensor anchor, rows;
  at::native::call_hydro_ref_x1(
      w.device().type(), w.contiguous(), dx1f.contiguous(), anchor, r.psf_lo,
      r.psf_hi, r.pref, r.dsf, r.dref, (int)w.size(-1) - 1, kGrav,
      snap::kX1RefUniform, /*phys_in=*/true, /*phys_out=*/true,
      /*wall_clamp=*/true, rows);
  return r;
}

//! The cells the brief asks for: up to roughly three scale heights thick.
//! 1.25 is in the list on purpose -- it is the one that CONVERGES at the base
//! commit and still breaks the solver, so dropping it would hide the second
//! half of the defect behind the first.
std::vector<double> thicknesses() { return {0.3, 1.0, 1.25, 1.5, 2.0, 3.0}; }

//! A one-column Cartesian block of `nx1` cells of width `dz`, walls at both x1
//! ends. `implicit_scheme` 0 is the explicit path, 1 the vertically implicit
//! one. Every float is written at full precision: at 6 significant digits the
//! block's dx1f differs from the column's in the 7th place, which is itself a
//! rest-state defect of ~1e-6 and would mask the one under test. `recon` is
//! the vertical (and horizontal) reconstruction; it is a parameter because the
//! long-run gate below separates the rest state from the reconstruction that
//! integrates it.
std::string write_card(int nx1, double dz, int implicit_scheme,
                       std::string const& recon = "weno5") {
  char fname[] = "/tmp/test-thick-cell-rest-XXXXXX";
  int fd = mkstemp(fname);
  EXPECT_NE(fd, -1);
  if (fd != -1) close(fd);
  std::ofstream o(fname);
  o << std::setprecision(17);
  o << "reference-state: {Tref: 0., Pref: 1.e5}\n"
    << "species:\n  - name: dry\n    composition: {H: 2}\n    cv_R: 2.5\n"
    << "geometry:\n  type: cartesian\n"
    << "  bounds: {x1min: 0., x1max: " << dz * nx1
    << ", x2min: 0., x2max: 1., x3min: 0., x3max: 1.}\n"
    << "  cells: {nx1: " << nx1 << ", nx2: 1, nx3: 1, nghost: " << kNg << "}\n"
    << "dynamics:\n"
    << "  equation-of-state: {type: ideal-gas, gammad: " << kGamma
    << ", weight: " << 8.31446261815324 / kRd
    << ", density-floor: 1.e-30, pressure-floor: 1.e-30, limiter: false}\n"
    << "  reconstruct:\n"
    << "    vertical: {type: " << recon << ", scale: false, shock: false}\n"
    << "    horizontal: {type: " << recon << ", scale: false, shock: false}\n"
    << "  riemann-solver: {type: lmars}\n"
    << "boundary-condition:\n"
    << "  external: {x1-inner: reflecting, x1-outer: reflecting}\n"
    << "integration: {type: rk3, cfl: 0.4, implicit-scheme: " << implicit_scheme
    << "}\n"
    << "forcing:\n  const-gravity: {grav1: -" << kGrav << "}\n";
  o.close();
  return fname;
}

struct Drift {
  double mach;   //!< max |v1| / c over every owned cell and every step
  double force;  //!< max |v1| / (g dt) after the FIRST step: the standing
                 //!< force the state still feels, in units of g, before any
                 //!< accumulation -- the well-balanced property proper
};

//! Step `nstep` times from `col` as the card's block. `mach` is normalised by
//! the sound speed because that is what "at rest" means for a compressible
//! column; an absolute m/s bound would be a different gate at every pressure
//! level. `force` is the tree's own idiom (test_balance_column,
//! test_x1_centroid_rest) and is the one of the two that isolates the
//! reference from the integrator.
Drift drift(torch::Tensor const& col, int nx1, double dz, int implicit_scheme,
            int nstep, std::string const& recon = "weno5") {
  auto fname = write_card(nx1, dz, implicit_scheme, recon);
  auto b = snap::MeshBlock(snap::MeshBlockOptionsImpl::from_yaml(fname));
  std::remove(fname.c_str());
  b->to(torch::kCPU, torch::kFloat64);
  auto pc = b->pcoord;
  int il = pc->il(), iu = pc->iu();

  // the block's own widths must be the ones the column was balanced against,
  // or this measures the deck's rounding instead of the reference
  auto dblk = pc->dx1f.to(torch::kFloat64);
  EXPECT_LT((dblk - dz).abs().max().item<double>(), 1.e-9 * dz)
      << "the deck's dx1f is not the column's";

  auto w = torch::zeros(
      {col.size(0), pc->options->nc3(), pc->options->nc2(), pc->options->nc1()},
      col.options());
  w.narrow(-1, il, nx1).copy_(col);
  for (int m = 0; m < il; ++m) {  // overwritten by the reflecting walls
    w.narrow(-1, m, 1).copy_(w.narrow(-1, il, 1));
    w.narrow(-1, iu + 1 + m, 1).copy_(w.narrow(-1, iu, 1));
  }

  snap::Variables v{{"hydro_w", w}};
  b->initialize(v);
  Drift d{0., 0.};
  for (int n = 0; n < nstep; ++n) {
    double dt = b->max_time_step(v);
    for (int s = 0; s < (int)b->pintg->stages.size(); ++s) b->forward(v, dt, s);
    auto end =
        b->phydro->peos->compute("U->W", {v.at("hydro_u")}).narrow(-1, il, nx1);
    auto cs = (kGamma * end[snap::IPR] / end[snap::IDN]).sqrt();
    d.mach = std::max(d.mach, (end[snap::IVX].abs() / cs).max().item<double>());
    if (n == 0)
      d.force = end[snap::IVX].abs().max().item<double>() / (kGrav * dt);
  }
  return d;
}

}  // namespace

// The fixed point has to EXIST and be reachable. rtol is 1e-13 rather than the
// 1e-10 default so the gate is the operator's own fixed point and not the
// tolerance: at the base commit a = 1.5 plateaus at 1.9e-01, which no
// tolerance in this range would accept, and a = 1.25 does reach 1e-13.
TEST(ThickCellRest,
     balance_column_converges_on_cells_up_to_three_scale_heights) {
  for (int nx1 : {5, 8, 9}) {
    for (double a : thicknesses()) {
      auto [w, dx1f] = isothermal_column(nx1, a);
      torch::Tensor wb;
      double err = -1.;
      int sweeps = -1;
      ASSERT_NO_THROW(std::tie(wb, err, sweeps) = snap::balance_column(
                          w, dx1f, kGrav, /*wall_clamp=*/true, /*rtol=*/1.e-13,
                          /*max_iter=*/5000, "cartesian", /*stretched=*/false))
          << "nx1=" << nx1 << " a=" << a;
      EXPECT_LT(err, 1.e-13) << "nx1=" << nx1 << " a=" << a;
      // and the state really is usable: positive, and the temperature held
      EXPECT_GT(wb[snap::IPR].min().item<double>(), 0.)
          << "nx1=" << nx1 << " a=" << a;
      auto rt0 = w[snap::IPR] / w[snap::IDN];
      auto rt1 = wb[snap::IPR] / wb[snap::IDN];
      EXPECT_LT(((rt1 - rt0).abs() / rt0).max().item<double>(), 1.e-14)
          << "nx1=" << nx1 << " a=" << a;
    }
  }
}

// The separate half: a column that DID converge must also be admissible, i.e.
// the face states the solver restores from it must be positive. At the base
// commit a = 1.25 converges to 9.4e-14 and still fails here, with the top wall
// face at -1.4e-01 Pa.
TEST(ThickCellRest, a_converged_column_has_positive_restored_wall_faces) {
  for (double a : thicknesses()) {
    auto [w, dx1f] = isothermal_column(8, a);
    torch::Tensor wb;
    double err;
    int sweeps;
    ASSERT_NO_THROW(std::tie(wb, err, sweeps) = snap::balance_column(
                        w, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false))
        << "a=" << a;

    // The reference the solver will rebuild from the RETURNED state, from the
    // same kernel balance_column iterates against.
    auto r = reference(wb, dx1f);
    int n = (int)wb.size(-1);
    auto pp = (wb[snap::IPR] - r.pref).flatten();
    double gauge = pp[n - 1].item<double>();  // p', read where the gauge is set

    // hydro_forward.cpp restores p' + psf_lo at every physical face and rho' +
    // dsf alongside it, then floors any non-positive result back to the bare
    // reference -- a finite jump of |p'| exactly at a wall. The faces run
    // il..iu+1, so psf_hi of the top cell is the last of them.
    auto faces = torch::cat(
        {r.psf_lo.flatten(), r.psf_hi.flatten().narrow(0, n - 1, 1)});
    double worst = (gauge + faces).min().item<double>();
    std::cout << std::scientific << "a=" << a << ": gauge p' = " << gauge
              << ", min restored face pressure = " << worst << '\n';
    EXPECT_GT(worst, 0.) << "a=" << a
                         << ": the solver's positivity floor fires at a wall";

    auto dfaces =
        torch::cat({r.dsf.flatten(), r.dsf.flatten().narrow(0, n - 1, 1)});
    double rho_gauge = (wb[snap::IDN] - r.dref).flatten()[n - 1].item<double>();
    EXPECT_GT((rho_gauge + dfaces).min().item<double>(), 0.) << "a=" << a;
  }
}

//! The deck for the solver checks: five cells, the fewest balance_column
//! accepts, so the COLUMN stays as shallow as cells of this thickness allow.
//! Depth is what costs precision here, not thickness: a five-cell column at
//! a = 3 already spans exp(12) = 1.6e5 in pressure between its end cells, and
//! the cancellation that holds the bottom cell at rest is carried in units of
//! the bottom cell's own pressure, so the top cell inherits ~eps times that
//! range however exact the reference is. Eight cells at a = 3 span exp(21) and
//! the same checks land two orders worse (measured).
constexpr int kSolverNx1 = 5;
constexpr int kSolverSteps = 50;

// The well-balanced property proper, across the whole thickness range and both
// integration paths: ONE step from the projected column, and the standing
// force it still feels in units of g. One step, so this is the reference's
// own error with no room for the integrator to amplify it.
//
// Measured on this branch (5 cells): 1.6e-14 at a = 0.3, rising with the
// column's pressure range to 1.0e-11 (explicit) and 9.9e-13 (implicit) at
// a = 3. At the base commit a = 1.25 gives 3.8e-01 -- the gate below
// discriminates by nine orders.
TEST(ThickCellRest, a_projected_thick_column_feels_no_standing_force) {
  torch::set_num_threads(1);
  for (double a : thicknesses()) {
    double dz = a * scale_height();
    auto [w, dx1f] = isothermal_column(kSolverNx1, a);
    torch::Tensor wb;
    double err;
    int sweeps;
    ASSERT_NO_THROW(std::tie(wb, err, sweeps) = snap::balance_column(
                        w, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false))
        << "a=" << a;
    ASSERT_LT(err, 1.e-13) << "a=" << a;

    for (int imp : {0, 1}) {
      auto d = drift(wb, kSolverNx1, dz, imp, /*nstep=*/1);
      std::cout << std::scientific << "a=" << a
                << (imp ? " implicit" : " explicit") << ": balance " << err
                << " in " << sweeps << " sweeps, one-step |a|/g " << d.force
                << '\n';
      EXPECT_LT(d.force, 1.e-10) << "a=" << a << " implicit-scheme=" << imp;
    }
  }
}

// And the drift a run actually accumulates over 50 steps. The bounds are split
// by scheme and by thickness because 1e-12 is NOT attainable everywhere in
// float64 on this deck, and asserting it where it is not would be asserting
// something no reference can deliver. What limits it is the column's pressure
// range, not the reference: the cancellation that holds a cell at rest is
// carried in units of that cell's pressure, so the top of a column spanning
// exp(12) inherits ~eps times that range whatever the reference does. Measured
// on this branch (5 cells, max over 50 steps):
//
//   a         0.3      1.0      1.25     1.5      2.0      3.0
//   implicit  2.7e-15  2.6e-14  4.3e-14  6.9e-14  1.1e-13  6.7e-12
//   explicit  3.7e-15  8.1e-14  1.8e-13  4.3e-13  2.9e-12  3.98e-06
//
// The implicit a = 3 run peaks at 6.7e-12 in transient acoustic ringing and
// then DECAYS to 3.3e-15 by the last step. The explicit a = 3 run instead
// grows exponentially from a roundoff-level seed (8.6e-12 at step 1 to 4.0e-06
// at step 50): the explicit integrator goes unstable on three-scale-height
// cells. That is not a standing force -- the one-step force above is 1.0e-11 --
// and it is precisely the regime the vertically implicit scheme exists for, so
// it is left to the standing-force check instead of being gated here.
TEST(ThickCellRest, a_projected_thick_column_does_not_drift) {
  torch::set_num_threads(1);
  for (double a : thicknesses()) {
    double dz = a * scale_height();
    auto [w, dx1f] = isothermal_column(kSolverNx1, a);
    auto [wb, err, sweeps] = snap::balance_column(w, dx1f, kGrav, true, 1.e-13,
                                                  5000, "cartesian", false);
    ASSERT_LT(err, 1.e-13) << "a=" << a;

    auto imp = drift(wb, kSolverNx1, dz, 1, kSolverSteps);
    std::cout << std::scientific << "a=" << a << " implicit: max |w|/c over "
              << kSolverSteps << " steps " << imp.mach << '\n';
    EXPECT_LT(imp.mach, a <= 2.0 ? 1.e-12 : 1.e-11) << "a=" << a << " implicit";

    auto exp_ = drift(wb, kSolverNx1, dz, 0, kSolverSteps);
    std::cout << std::scientific << "a=" << a << " explicit: max |w|/c over "
              << kSolverSteps << " steps " << exp_.mach << '\n';
    if (a <= 1.5) {
      EXPECT_LT(exp_.mach, 1.e-12) << "a=" << a << " explicit";
    } else if (a <= 2.0) {
      EXPECT_LT(exp_.mach, 1.e-11) << "a=" << a << " explicit";
    }
  }
}

//! 10,000 steps is where an amplifier shows and 50 steps does not: at
//! e^(+5.5e-04) per step, the rate measured at dz/H = 1, fifty steps multiply a
//! perturbation by 1.03 and ten thousand by 245. Each run below costs about
//! 9 s at kSolverNx1 on one thread, which is why the long gate takes the five
//! rungs and the two paths that hold rather than the whole cross product.
constexpr int kLongSteps = 10000;

// What balance_column RETURNS has to be the fixed point, not merely the first
// sweep that dips under rtol. The sweeps converge geometrically with a tail
// factor of 0.42 to 0.63, so those are two different states two to three
// orders apart: at dz/H = 1, nx1 = 8, sweep 34 gives 7.618e-14 and sweep 40
// gives 2.481e-16. The solver reconstructs p - pref, so the leftover is the
// momentum the state injects into itself every step, and on cells of about a
// scale height the explicit path amplifies it.
//
// The gate is therefore the residual's own floor, plus idempotence: feeding
// the answer back in must not buy another order. Before the stopping rule the
// second call returned the same state in ZERO sweeps -- the loose state is a
// fixed point of the stopping rule, not of the iteration -- so idempotence
// alone cannot see this; it is kept to pin the new rule against an iteration
// that wanders at the floor. Measured, nx1 = 8, dz/H = 1: residual 7.618e-14
// in 34 sweeps before, 2.481e-16 in 41 after.
TEST(ThickCellRest, balance_column_returns_the_fixed_point_not_the_first_pass) {
  for (int nx1 : {5, 8}) {
    for (double a : thicknesses()) {
      auto [w, dx1f] = isothermal_column(nx1, a);
      auto [wb, err, sweeps] = snap::balance_column(
          w, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false);
      // re-project the answer: a fixed point cannot be improved on
      auto [wb2, err2, sweeps2] = snap::balance_column(
          wb, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false);
      std::cout << std::scientific << "nx1=" << nx1 << " a=" << a
                << ": residual " << err << " in " << sweeps << " sweeps, "
                << "re-projected " << err2 << " in " << sweeps2 << '\n';
      EXPECT_LT(err, 1.e-14) << "nx1=" << nx1 << " a=" << a
                             << ": the returned residual is not at its floor";
      EXPECT_GT(err2, 0.1 * err)
          << "nx1=" << nx1 << " a=" << a
          << ": re-projecting bought another order, so the state returned the "
             "first time was not the fixed point";
    }
  }
}

// The end-to-end gate the brief asks for: from a converged projection, over
// 10,000 steps, residual <= 1e-13 and max |w|/c <= 1e-12, on cells up to three
// scale heights, in BOTH integration paths and on the tree's DEFAULT deck --
// weno5 vertical reconstruction, lmars, rk3 at cfl 0.4.
//
// Three things had to be true for this to hold and each is pinned elsewhere in
// this file: the reference has a discrete rest state past one scale height
// (the log-mean gate), balance_column returns its fixed point rather than the
// first state under rtol (the case above), and a cell past the gate takes a
// limited x1 reconstruction of the pressure perturbation. Without the last of
// those the EXPLICIT weno5 arm measures 1.569e-03 at dz/H = 1.5, 1.988 at 2
// and 9.134e-01 at 3 (and 5.931e-13 at 1, which squeaks under the bound), so
// three of the six rungs fail.
//
// 0.75 is in the list because it is the gate's own value, where the cell is
// NOT past the bound and so still takes the unlimited reconstruction: its
// number is bitwise the same with the guard and without it.
//
// Measured here (nx1 = 5, max |w|/c over 10,000 steps, zero rejected steps):
//
//   dz/H              0.3      0.75     1.0      1.5      2.0      3.0
//   explicit, weno5   8.0e-16  3.7e-15  4.6e-16  1.4e-15  1.2e-15  5.1e-15
//   implicit, weno5   3.4e-16  4.3e-16  5.9e-16  4.2e-16  4.0e-16  4.0e-15
TEST(ThickCellRest, a_projected_column_holds_for_ten_thousand_steps) {
  torch::set_num_threads(1);
  for (double a : {0.3, 0.75, 1.0, 1.5, 2.0, 3.0}) {
    double dz = a * scale_height();
    auto [w, dx1f] = isothermal_column(kSolverNx1, a);
    auto [wb, err, sweeps] = snap::balance_column(w, dx1f, kGrav, true, 1.e-13,
                                                  5000, "cartesian", false);
    ASSERT_LT(err, 1.e-13) << "a=" << a;

    for (int imp : {0, 1}) {
      auto d = drift(wb, kSolverNx1, dz, imp, kLongSteps);
      std::cout << std::scientific << "a=" << a
                << (imp ? " implicit" : " explicit") << " weno5: max |w|/c "
                << d.mach << " over " << kLongSteps << " steps\n";
      EXPECT_LT(d.mach, 1.e-12) << "a=" << a << " implicit-scheme=" << imp;
    }
  }
}

// The limited reconstruction past the gate is a STABILITY guard, not a
// substitute for the rest state: a monotone deck from end to end has to clear
// the same bar, or the case above could be passing on the limiter alone with a
// broken projection underneath. plm at the thickest rung, both paths.
TEST(ThickCellRest,
     a_monotone_deck_holds_the_same_bound_at_three_scale_heights) {
  torch::set_num_threads(1);
  double a = 3.0, dz = a * scale_height();
  auto [w, dx1f] = isothermal_column(kSolverNx1, a);
  auto [wb, err, sweeps] = snap::balance_column(w, dx1f, kGrav, true, 1.e-13,
                                                5000, "cartesian", false);
  ASSERT_LT(err, 1.e-13);
  for (int imp : {0, 1}) {
    auto d = drift(wb, kSolverNx1, dz, imp, kLongSteps, "plm");
    std::cout << std::scientific << "a=" << a
              << (imp ? " implicit" : " explicit") << " plm:   max |w|/c "
              << d.mach << " over " << kLongSteps << " steps\n";
    EXPECT_LT(d.mach, 1.e-12) << "plm implicit-scheme=" << imp;
  }
}

// The thickness gate is read off the ITERATE: g rho dz / p, with rho recovered
// as p / rt. That is p/rho-invariant in exact arithmetic but only to ~1 ulp in
// float64, so a column sitting EXACTLY at kX1RefMaxThickness has cells on both
// sides of `thick <= bound` and flips side between sweeps: two operators, no
// fixed point. Measured at dz/H = 0.75 with a strict comparison, nx1 = 8: the
// sweeps plateau at 1.6e-03, while 0.75 +/- 1e-09 converge in 47 and 27
// sweeps. Any value the bound takes is a deck someone writes -- 0.75 most of
// all -- so the comparison carries a tolerance far above that wobble
// (kX1RefThicknessTol) and the deck AT the bound deterministically takes the
// <= side the bound documents.
TEST(ThickCellRest, a_column_exactly_at_the_thickness_gate_still_converges) {
  torch::set_num_threads(1);
  const double a = snap::kX1RefMaxThickness;
  for (int nx1 : {5, 8, 9}) {
    auto [w, dx1f] = isothermal_column(nx1, a);
    torch::Tensor wb;
    double err = -1.;
    int sweeps = -1;
    ASSERT_NO_THROW(std::tie(wb, err, sweeps) = snap::balance_column(
                        w, dx1f, kGrav, true, 1.e-13, 5000, "cartesian", false))
        << "nx1=" << nx1 << " at the gate a=" << a;
    std::cout << std::scientific << "gate a=" << a << " nx1=" << nx1
              << ": balance " << err << " in " << sweeps << " sweeps\n";
    EXPECT_LT(err, 1.e-13) << "nx1=" << nx1 << " at the gate a=" << a;
  }
  // and the column at the bound is still a rest state in both schemes
  auto [w, dx1f] = isothermal_column(kSolverNx1, a);
  auto [wb, err, sweeps] = snap::balance_column(w, dx1f, kGrav, true, 1.e-13,
                                                5000, "cartesian", false);
  ASSERT_LT(err, 1.e-13);
  for (int imp : {0, 1}) {
    auto d = drift(wb, kSolverNx1, a * scale_height(), imp, kSolverSteps);
    std::cout << std::scientific << "gate a=" << a
              << (imp ? " implicit" : " explicit") << ": max |w|/c " << d.mach
              << ", one-step |a|/g " << d.force << '\n';
    EXPECT_LT(d.mach, 1.e-12) << "implicit-scheme=" << imp;
    EXPECT_LT(d.force, 1.e-10) << "implicit-scheme=" << imp;
  }
}

// The control: the SAME end-to-end gate must see the defect it exists to
// remove, or it could pass on a build where nothing is balanced at all. A
// column marched through the continuum ODE satisfies the continuum balance,
// not the discrete one, and must fail the 1e-12 gate.
TEST(ThickCellRest, the_unprojected_column_fails_the_same_gates) {
  torch::set_num_threads(1);
  double a = 1.0, dz = a * scale_height();
  auto [w, dx1f] = isothermal_column(kSolverNx1, a);
  auto d = drift(w, kSolverNx1, dz, /*implicit_scheme=*/0, kSolverSteps);
  std::cout << std::scientific << "unprojected a=" << a << ": max |w|/c "
            << d.mach << ", one-step |a|/g " << d.force << '\n';
  EXPECT_GT(d.mach, 1.e-12);
  EXPECT_GT(d.force, 1.e-10);
}

// geometry/cells/x1rat builds its faces from expm1, so adjacent width ratios
// come out as q (1 + O(eps)). A STRICT ratio <= kX1MaxWidthRatio therefore
// rejects the documented boundary value itself: measured excess 1.1e-15 at
// nx1 = 5 rising to 2.7e-14 at nx1 = 100, at every nx1 tried. The guard has to
// be inclusive to a tolerance that still rejects a real violation.
TEST(ThickCellRest, the_x1rat_width_ratio_guard_admits_its_own_boundary) {
  const double qmax = snap::CoordinateOptionsImpl::kX1MaxWidthRatio;
  for (int nx1 : {5, 8, 16, 32, 64, 100}) {
    char fname[] = "/tmp/test-thick-cell-x1rat-XXXXXX";
    int fd = mkstemp(fname);
    ASSERT_NE(fd, -1);
    close(fd);
    {
      std::ofstream o(fname);
      o << std::setprecision(17);
      o << "geometry:\n  type: cartesian\n"
        << "  bounds: {x1min: 0., x1max: 1.e6, x2min: 0., x2max: 1., "
           "x3min: 0., x3max: 1.}\n"
        << "  cells: {nx1: " << nx1 << ", nx2: 1, nx3: 1, nghost: " << kNg
        << ", x1rat: " << qmax << "}\n";
    }
    std::shared_ptr<snap::CoordinateOptionsImpl> op;
    EXPECT_NO_THROW(op = snap::CoordinateOptionsImpl::from_yaml(fname))
        << "x1rat = kX1MaxWidthRatio = " << qmax << " at nx1 = " << nx1;
    std::remove(fname);
  }
}

// ...and the control, so the line above is not simply "the guard is gone": a
// ratio clearly past the bound is still refused.
TEST(ThickCellRest,
     the_x1rat_width_ratio_guard_still_refuses_a_real_violation) {
  const double qmax = snap::CoordinateOptionsImpl::kX1MaxWidthRatio;
  char fname[] = "/tmp/test-thick-cell-x1rat-bad-XXXXXX";
  int fd = mkstemp(fname);
  ASSERT_NE(fd, -1);
  close(fd);
  {
    std::ofstream o(fname);
    o << std::setprecision(17);
    o << "geometry:\n  type: cartesian\n"
      << "  bounds: {x1min: 0., x1max: 1.e6, x2min: 0., x2max: 1., "
         "x3min: 0., x3max: 1.}\n"
      << "  cells: {nx1: 16, nx2: 1, nx3: 1, nghost: " << kNg
      << ", x1rat: " << qmax * 1.001 << "}\n";
  }
  EXPECT_THROW(snap::CoordinateOptionsImpl::from_yaml(fname), std::exception);
  std::remove(fname);
}
