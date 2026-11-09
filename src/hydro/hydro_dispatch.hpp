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

//! Largest cell hydrostatic thickness, g rho dz / p = dz / H, that the x1
//! reference quadratures from SIX FACE PRESSURES, and that hydro_forward.cpp
//! reconstructs with the deck's unlimited stencil.
//!
//! Those six faces span exp(5 dz/H) while the cell's own [psf_hi, psf_lo]
//! bracket is exp(-dz/H) of its lower face, so past this bound the quadrature
//! leaves the bracket and the arithmetic mean it falls back to has no
//! discrete rest state; the reference takes the log-mean there instead, and
//! the reconstruction a limited slope. 0.75 keeps a 96% margin on the first
//! quantity to bite, the restored wall face p' + psf_lo, and leaves every
//! deck in this tree on the unchanged path (happysky19/snapy#5).
constexpr double kX1RefMaxThickness = 0.75;

//! Relative slack on that comparison, so the BOUND ITSELF is on the <= side.
//!
//! balance_column holds p/rho fixed per cell only to ~1 ulp, so a column
//! written exactly at the bound would otherwise have cells on both sides of a
//! strict test and flip between sweeps: measured, dz/H = 0.75 then plateaus
//! at 1.6e-03 while 0.75 +/- 1e-09 converge below 1e-13.
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
