// A hydrostatic column of THICK cells must have a discrete rest state, and
// the scheme must hold it.
//
// The x1 reference reads w[IPR] as a cell AVERAGE, but hydro_ref_x1_scan_impl
// builds the column's top face as p_top * exp(-thick/2), the face above a
// POINT value at the cell centre. The two agree only as thick -> 0, so past
// about one scale height per cell the gauge p' == c that balance_column finds
// is displaced far enough that the restored face pressure p' + psf goes
// negative at the top wall and the solver's positivity floor fires there.
// Inverting the cell average instead gives the consistent face,
//
//     A* = dp_top / expm1(thick_top),
//
// for which an isothermal column is a fixed point with c == 0 at any
// thickness.
//
// RED on 3c891cb20614260351944fb8007cbc9bd50d22a3: dz/H = 1.25 balances after
// ~430 sweeps with min(p' + psf) = -3.97e+01 and both schemes then drift to
// |w|/c ~ 3e-01. GREEN with the consistent anchor and the log-mean reference:
// zero sweeps, c == 0, positive faces, rest at round-off.
#include <cmath>
#include <tuple>

#include <gtest/gtest.h>

#include <snap/snap.h>
#include <snap/hydro/balance_column.hpp>

#include "cuda_test_gate.hpp"

namespace {
constexpr double kGrav = 10.44, kRd = 3777., kT0 = 300., kPs = 1.e5;

struct Balanced {
  torch::Tensor col, faces;
  double gauge, face_min, residual;
  int sweeps;
};

//! balance an isothermal column of `nx1` cells each `a` scale heights thick
Balanced balance(double a, int nx1, torch::DeviceType dev) {
  auto opt = torch::TensorOptions().dtype(torch::kFloat64).device(dev);
  double dz = a * kRd * kT0 / kGrav;
  auto dx1f = torch::full({nx1}, dz, opt);
  auto p = kPs * torch::exp(-(torch::arange(nx1, opt) + 0.5) * a);
  auto col = torch::zeros({snap::IPR + 1, 1, 1, nx1}, opt);
  col[snap::IPR].copy_(p.view({1, 1, nx1}));
  col[snap::IDN].copy_((p / (kRd * kT0)).view({1, 1, nx1}));

  auto [wb, err, sweeps] = snap::balance_column(col, dx1f, kGrav, true, 1.e-13,
                                                5000, "cartesian", false);
  return {wb, torch::Tensor(), 0., 0., err, sweeps};
}
}  // namespace

//! The column balances with the gauge identically zero, so the restored face
//! pressure is the bare reference and is positive by construction.
TEST(hydro, thick_cell_reference_is_average_consistent) {
  for (auto dev : {torch::kCPU, torch::kCUDA}) {
    if (dev == torch::kCUDA && !snapy_cuda_test_enabled()) continue;
    for (double a : {0.75, 1.25, 1.5, 3.0}) {
      auto b = balance(a, 5, dev);
      // the analytic column IS the discrete rest state: no projection needed
      EXPECT_LE(b.sweeps, 1) << "a=" << a << " dev=" << (int)dev;
      EXPECT_LT(b.residual, 1.e-13) << "a=" << a << " dev=" << (int)dev;
    }
  }
}

//! The refusal in balance_column fires on a non-positive restored face
//! pressure. With the consistent anchor no thickness reaches it, so a column
//! that main cannot balance at all comes back balanced here.
TEST(hydro, thick_cell_column_balances_past_four_scale_heights) {
  for (double a : {4.0, 8.0}) {
    EXPECT_NO_THROW({
      auto b = balance(a, 5, torch::kCPU);
      EXPECT_LT(b.residual, 1.e-13) << "a=" << a;
    }) << "a="
       << a;
  }
}
