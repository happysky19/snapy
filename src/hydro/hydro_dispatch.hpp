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

//! Validity bound of the factored rows, in cell widths per H_ref.
//! The row weights carry e^{(t_max - t_min) dz_i / H_ref}, so they grow with
//! the cell's own thickness while H_ref is one value for the run. Up to this
//! bound the row still returns the exponential it is built to be exact for to
//! round-off; past it the weights lose that and finally overflow. Measured on
//! this function (uniform column, nc1 = 5 and 9, row evaluated on
//! p = e^{-z/H_ref}, worst cell): the relative error is <= 4.2e-16 at every
//! dz/H_ref up to 20, then 5.0e-14 at 25, 2.7e-12 at 30, 8.2e-10 at 40,
//! 2.6e-05 at 80, and the weights themselves are not finite from about 140
//! (max|c_m| 1.1e+40 at 20, 8.1e+82 at 40, 5.1e+255 at 120, inf at 150).
//! A cell past the bound gets no row (start < 0) and keeps the log-mean of its
//! own two faces, which is exact for a column that IS e^{-z/H_ref} and is what
//! the branch computed before rows existed.
//!
//! Those figures are DOUBLE precision: the table is built in float64 here and
//! converted with .to(w.options()) in hydro.cpp, so a float32 run loses the
//! largest weights to +-inf earlier. Measured by bisection on this function,
//! max|c_m| passes FLT_MAX at dz/H_ref = 19.2934 (8.1e+37 at 19.0, 2.2e+38 at
//! 19.2, 3.5e+38 at 19.3), i.e. just inside the bound. That failure is safe --
//! an infinite weight makes the row's bracket comparison false and the cell
//! keeps the same log-mean the guard would have given it -- and a cell 19
//! scale heights thick is not a float32 column anyway, so the bound is left at
//! the double figure rather than made dtype-dependent.
constexpr double kX1RefMaxFactoredThickness = 20.0;

torch::Tensor hydro_ref_x1_stretched_rows(torch::Tensor const& dx1f, int iu,
                                          bool phys_in, bool phys_out,
                                          bool wall_clamp);
torch::Tensor hydro_ref_x1_factored_rows(torch::Tensor const& dx1f, int iu,
                                         bool phys_in, bool phys_out,
                                         bool wall_clamp, double href);

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
