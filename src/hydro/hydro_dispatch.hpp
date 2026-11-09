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
//! The test is on p/rho, which balance_column holds FIXED per cell, so the
//! branch taken cannot oscillate along its fixed-point iteration -- that is
//! what makes the fixed point exist and be reachable.
constexpr double kX1RefMaxThickness = 0.75;

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
