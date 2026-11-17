#pragma once
// V3 lane C skeleton (declarations only; not built). One definition of every
// x1 weight: reconstruction rows, conversion-order 4 (L), key-4 wall ghosts,
// the wb_ref4 face density and the stretched six-face reference rows. All are
// built once per grid on the host in double from x1f and cached per device
// and dtype. Replaces x1_coeffs.*, wb_ref4_stencils, wall4_weights,
// conv4_x1_weights, hydro_ref_x1_stretched_rows and balance_column's lap.

namespace snap {

//! weights of the cell averages on faces[k..k+n] that give the value at x
//! of the polynomial whose primitive interpolates them (x1_coeffs.cpp
//! primitive_row and wb_ref4.cpp lagrange_deriv are this one function)
void face_value_row(double const* faces, int n, double x, double* w);

//! a scheme's coefficient table: cm/cp, rows (nface, ncoeff), or one row
//! broadcast with row_stride 0 on a uniform grid (no second dispatch path)
struct ReconRows {
  Scheme scheme;
  torch::Tensor cm, cp;
  int64_t row_stride = 0;
};
ReconRows recon_rows(Scheme s, torch::Tensor const& x1f_or_undefined);

//! conversion order 4: L a = h^2/24 q'' as {kp, km} per cell
std::pair<torch::Tensor, torch::Tensor> conv4_rows(torch::Tensor const& x1f);

//! key-4 reflecting-wall parity ghosts, E[side][constraint] (hydro_forward.cpp
//! wall4_weights); constraint 0 cubic, 1 odd v, 2 even rho', 3 even p'
torch::Tensor wall4_rows(torch::Tensor const& x1f, int is, int iu, int ng);

//! conversion-order 4 face density of the cell reference (wb_ref4.cpp)
struct FaceDensityRows {
  bool usable = false, clamp_in = false, clamp_out = false;
  torch::Tensor idx, wt, counted;
};
FaceDensityRows face_density_rows(torch::Tensor const& x1f, int is, int iu,
                                  bool clamp_in, bool clamp_out);

//! stretched reference: six-face cell average per cell, (nc1, 7)
torch::Tensor six_face_rows(torch::Tensor const& dx1f, int iu, bool phys_in,
                            bool phys_out, bool wall_clamp);

//! cache key: x1f identity and _version, device, dtype (one rule, replacing
//! the four ad hoc staleness tests in hydro.cpp and hydro_forward.cpp)
struct X1RowsCache;

}  // namespace snap
