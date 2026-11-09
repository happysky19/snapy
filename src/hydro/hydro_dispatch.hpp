#pragma once

// torch
#include <ATen/native/DispatchStub.h>
#include <torch/torch.h>

namespace snap {

enum X1RefGrid : int {
  kX1RefNonUniform = 0,
  kX1RefUniform = 1,
  kX1RefStretched = 2
};

//! Largest cell hydrostatic thickness, g rho dz / p = dz / H in scale heights,
//! for which the x1 reference quadratures a cell from SIX FACE PRESSURES.
//!
//! Those six faces span exp(5 dz/H) in pressure while the cell's own bracket
//! [psf_hi, psf_lo] is only exp(-dz/H) of its lower face, so the quadrature's
//! cancellation error grows like exp(k dz/H) relative to the bracket that
//! judges it: the one-sided wall rows leave the bracket near dz/H ~ 1.3 and
//! the centred row near ~2.5. Past this bound the reference is the log-mean of
//! the cell's two faces instead -- strictly inside the bracket, and the exact
//! cell average of a hydrostatic isothermal column at ANY thickness, so it has
//! a discrete rest state where the polynomial has none.
//!
//! 0.75 holds a 96% margin on the one quantity that bites first (the restored
//! wall face pressure p' + psf_lo, which goes negative by dz/H ~ 1.25) and
//! leaves every deck in this tree on the polynomial path.
//!
//! The same bound also gates the x1 RECONSTRUCTION of the pressure
//! perturbation in hydro_forward.cpp: past it the unlimited high-order
//! reconstruction is unstable in the explicit path (measured growth per step
//! e^(+4.9e-04) at dz/H = 0.75 rising to e^(+6.0e-03) at 1.5, against
//! e^(-5.8e-05) at 0.5), so a cell past the bound takes a limited one. The
//! two uses share a bound because they share a cause: a cell this thick
//! carries a dz/H-sized share of its own reference, so neither a polynomial
//! quadrature of its faces nor an unlimited stencil across them is trustworthy
//! any more.
//!
//! The test is on p/rho, which balance_column holds FIXED per cell, so the
//! branch taken cannot oscillate along its fixed-point iteration -- that is
//! what makes the fixed point exist and be reachable.
constexpr double kX1RefMaxThickness = 0.75;

//! Relative slack on the comparison against kX1RefMaxThickness.
//!
//! balance_column holds p/rho fixed per cell only to ~1 ulp -- it recovers rho
//! as p/rt from an iterate p that moves every sweep -- so the thickness the
//! kernel reads back wobbles in the last bit. A column written EXACTLY at the
//! bound then has cells on both sides of a strict comparison, flipping side
//! between sweeps, and the iteration has no fixed point to reach: measured at
//! dz/H = 0.75, nx1 = 8, the sweeps plateau at 1.6e-03 while 0.75 +/- 1e-09
//! both converge below 1e-13. 1e-09 is seven orders above that wobble and
//! seven below the margin the bound itself carries, so the deck at the bound
//! takes the <= side the bound documents.
constexpr double kX1RefThicknessTol = 1.e-9;

torch::Tensor hydro_ref_x1_stretched_rows(torch::Tensor const& dx1f, int iu,
                                          bool phys_in, bool phys_out,
                                          bool wall_clamp);

}  // namespace snap

namespace at::native {

using hydro_ref_x1_fn =
    void (*)(torch::Tensor const& w, torch::Tensor const& dx1f,
             torch::Tensor const& anchor, torch::Tensor const& psf_lo,
             torch::Tensor const& psf_hi, torch::Tensor const& pref,
             torch::Tensor const& dsf, torch::Tensor const& dref, int iu,
             double grav, int x1_grid, bool phys_in, bool phys_out,
             bool wall_clamp, torch::Tensor const& rows);

DECLARE_DISPATCH(hydro_ref_x1_fn, call_hydro_ref_x1);

}  // namespace at::native
