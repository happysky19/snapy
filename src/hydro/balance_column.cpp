// C/C++
#include <limits>

// snap
#include <snap/snap.h>

#include <snap/coord/x1_centroid.hpp>

#include "balance_column.hpp"
#include "hydro_dispatch.hpp"

namespace snap {

std::tuple<torch::Tensor, double, int> balance_column(
    torch::Tensor const& w, torch::Tensor const& dx1f, double grav,
    bool wall_clamp, double rtol, int max_iter, std::string const& geometry,
    bool stretched) {
  TORCH_CHECK(grav > 0., "balance_column: grav is a downward magnitude (> 0)");
  TORCH_CHECK(w.dim() == 4, "balance_column: w must be (nvar, nc3, nc2, nx1)");
  TORCH_CHECK(w.size(0) > IPR, "balance_column: w has no pressure channel");
  TORCH_CHECK(dx1f.dim() == 1 && dx1f.size(0) == w.size(-1),
              "balance_column: dx1f must be (nx1,) and match w's last dim");
  TORCH_CHECK(
      dx1f.scalar_type() == w.scalar_type() && dx1f.device() == w.device(),
      "balance_column: dx1f and w must share dtype and device");
  TORCH_CHECK(rtol > 0. && max_iter > 0,
              "balance_column: rtol and max_iter must be positive");
  // without the clamp the reference's wall rows quadrature faces below the
  // wall, which a ghost-free column does not have
  TORCH_CHECK(wall_clamp,
              "balance_column needs dynamics/wb-wall-clamp: without it the "
              "reference reads faces outside the column at each wall, so the "
              "balance found here is not the one the solver would enforce.");
  // no r^2 -> plain-mean conversion here (balance_column.hpp)
  TORCH_CHECK(!x1_centroid_exact_enabled() || geometry == "cartesian",
              "balance_column: under SNAP_X1_CENTROID_EXACT only a column "
              "declared geometry='cartesian' is balanced here, got '",
              geometry,
              "'; a spherical-polar column's rest state is the solver's own "
              "reference");

  int nc1 = w.size(-1);
  // below five the kernel's own thin-block fallback takes over and the answer,
  // though self-consistent, is not the one any real block would enforce; at
  // nc1 == 1 the gauge cell is the only cell and this would return "already
  // balanced" having done nothing
  TORCH_CHECK(nc1 >= 5, "balance_column: a column needs at least 5 cells, got ",
              nc1);
  auto wb = w.contiguous().clone();
  auto dxf = dx1f.contiguous();
  auto rho = wb[IDN];
  auto prs = wb[IPR];
  TORCH_CHECK(prs.min().item<double>() > 0. && rho.min().item<double>() > 0.,
              "balance_column: p and rho must be positive everywhere");
  auto rt = (prs / rho).clone();  // p/rho per cell, the invariant, taken ONCE

  auto sizes = w.sizes().slice(1).vec();
  auto psf_lo = torch::empty(sizes, w.options());
  auto psf_hi = torch::empty(sizes, w.options());
  auto pref = torch::empty(sizes, w.options());
  auto dsf = torch::empty(sizes, w.options());
  auto dref = torch::empty(sizes, w.options());
  torch::Tensor anchor;  // undefined: the kernel builds its own top anchor

  // unequal widths take the stretched rows (#280), whatever the key
  auto d = dxf.to(torch::kCPU).to(torch::kFloat64);
  stretched = stretched || (d.max() - d.min()).item<double>() >=
                               1.e-10 * d.mean().item<double>();
  int x1_grid = stretched ? kX1RefStretched : kX1RefUniform;
  // #280 (iv): the same rows a block builds from the same widths
  torch::Tensor rows;
  if (stretched)
    rows = hydro_ref_x1_stretched_rows(dxf, nc1 - 1, true, true, wall_clamp)
               .to(w.options());
  auto wgt = grav * dxf;

  // Is any cell of this column past the thickness gate? g rho dz / p is
  // g dz / rt, and rt is held fixed per cell, so this is a property of the
  // column the caller handed in, decided once.
  //
  // It decides whether the sweeps below stop at the first state under `rtol`,
  // as they always have, or carry on to the fixed point. Driving every column
  // to its fixed point would be strictly more accurate, but it would also
  // change the state returned to EVERY existing caller, and what that buys is
  // only worth having where the solver amplifies the leftover: past this
  // bound the explicit path grows a perturbation at e^(+4.9e-04) per step and
  // up, below it the same measurement damps (hydro_dispatch.hpp). So a column
  // that stays under the bound keeps the answer it has always had, bit for
  // bit -- measured on the cubed-sphere convection example, which projects
  // its initial condition here at rtol 1e-11 and whose cells are all at
  // g rho dz / p = 0.0083.
  bool thick_regime =
      ((wgt / rt) > kX1RefMaxThickness * (1. + kX1RefThicknessTol))
          .any()
          .item<bool>();

  // check, then update: the residual therefore describes the state returned,
  // and a column already at the fixed point comes back after zero updates
  double err = std::numeric_limits<double>::infinity();
  double prev = std::numeric_limits<double>::infinity();
  int sweeps = 0;
  for (; sweeps <= max_iter; ++sweeps) {
    at::native::call_hydro_ref_x1(wb.device().type(), wb, dxf, anchor, psf_lo,
                                  psf_hi, pref, dsf, dref, nc1 - 1, grav,
                                  x1_grid, /*phys_in=*/true, /*phys_out=*/true,
                                  wall_clamp, rows);
    auto pp = prs - pref;
    auto c = pp.narrow(-1, nc1 - 1, 1);  // one gauge per column, at its top
    err = ((pp - c).abs() / (rho * wgt)).max().item<double>();
    // A thin column stops at the first sweep under `rtol`, as it always has.
    // A column past the thickness gate carries on to the FIXED POINT.
    //
    // The sweeps converge geometrically with a measured tail factor of 0.42 to
    // 0.63, so those are two different states: at dz/H = 1, nx1 = 8, sweep 34
    // gives 7.618e-14 and sweep 40 gives 2.481e-16, the floor. The gap is not
    // cosmetic where the solver amplifies it. The solver reconstructs
    // p - pref, so whatever is left of p' - c is the per-step momentum the
    // state injects into itself, and past the gate the explicit path grows it
    // (measured e^(+5.5e-04) per step at dz/H = 1, e^(+2.9e-03) at 1.25);
    // over 10,000 steps at dz/H = 1 the drift goes from 1.159e-12 to
    // 2.011e-14 purely from the extra sweeps. Below the gate the same
    // measurement damps, so there the extra precision buys nothing that would
    // justify moving every existing caller's answer.
    //
    // Past the gate: keep sweeping while the residual is still being bought
    // down. 0.9 sits above every measured tail factor and below the floor's,
    // where the residual alternates between two neighbouring values (ratios
    // 0.76 and 1.32 at dz/H = 1.5) and so is left within a sweep or two.
    // `rtol` is then the tolerance that must be MET rather than the point at
    // which the iteration gives up.
    //
    // The no-op test keeps the documented invariant above: a column handed
    // back its own answer would otherwise spend one sweep discovering that the
    // residual cannot improve, and return sweeps = 1 where it has always
    // returned 0. At the fixed point the update reproduces the state bitwise,
    // so this reads "nothing left to do" directly instead of inferring it.
    auto next = pref + c;
    bool settled =
        !thick_regime || !(err < 0.9 * prev) || torch::equal(prs, next);
    if ((err < rtol && settled) || sweeps == max_iter) break;
    prev = err;
    prs.copy_(next);
    rho.copy_(prs / rt);
    // a diverging column walks its top cells to vacuum, and once rho goes
    // negative the residual above goes negative with it and reads as converged
    TORCH_CHECK(
        prs.min().item<double>() > 0.,
        "balance_column: the projection drove the pressure non-positive "
        "on sweep ",
        sweeps, " -- the column is diverging, not converging.");
  }

  TORCH_CHECK(err < rtol, "balance_column: no discrete balance after ", sweeps,
              " sweeps; residual bound on |a|/g is ", err, " > ", rtol);
  return {wb, err, sweeps};
}

}  // namespace snap
