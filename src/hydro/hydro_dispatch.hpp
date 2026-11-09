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

//! Largest cell thickness g rho dz / p = dz/H that the x1 reference
//! quadratures from SIX FACE PRESSURES and hydro_forward.cpp reconstructs
//! with the deck's unlimited stencil. Those faces span exp(5 dz/H) while the
//! cell's own bracket is exp(-dz/H) of its lower face, so past this bound the
//! quadrature leaves the bracket and its arithmetic-mean fallback has no
//! discrete rest state: the reference takes the log-mean there and the
//! reconstruction a limited slope. 0.75 keeps a 96% margin on the first
//! quantity to bite, the restored wall face. At each deck's coldest declared
//! temperature every examples/ deck stays on the unchanged path (the thickest,
//! uranus.yaml, is 0.154) and of the tests/ decks only
//! test_abnormal_exit_floor.yaml crosses, at 1.9, and that one exists to abort
//! on its pressure floor (happysky19/snapy#5).
constexpr double kX1RefMaxThickness = 0.75;

//! Relative slack on that comparison, so the BOUND ITSELF is on the <= side:
//! balance_column holds p/rho fixed only to ~1 ulp, so a column written
//! exactly at the bound would otherwise straddle a strict test and flip
//! between sweeps (dz/H = 0.75 then plateaus at 1.6e-03). This is a
//! double-precision guarantee: in a float instantiation 0.75 * (1 + 1e-9)
//! rounds back to 0.75f, so there the comparison is strict again.
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
