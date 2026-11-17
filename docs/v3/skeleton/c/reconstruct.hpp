#pragma once
// V3 lane C skeleton (declarations only; not built). Reconstruction as one
// module with three stages that today live in hydro_forward.cpp: conversion
// (order 2/4 and key-4 wall fills), the well-balanced x1 split, and the face
// floors. The Interp class hierarchy (7 classes) becomes a Scheme per group.

namespace snap {

struct ReconstructOptionsImpl {
  ADD_ARG(std::string, type) = "dc";  // dc|plm|cp3|weno3|cp5|weno5
  ADD_ARG(bool, scale) = false;
  ADD_ARG(bool, shock) = false;       // one default (today true vs false)
};

//! the faces of one sweep: lr[ILT|IRT], plus what the floors did
struct FaceStates {
  torch::Tensor lr;      // (2, nvar, nc3, nc2, nc1)
  torch::Tensor floors;  // int64 (3,): rho, p, species faces floored (EF)
};

//! conversion-order 2 (identity) or 4: w = W(u - L u) + L W(u), the key-4
//! wall ghosts and the per-cell fallback; used by the solver and by
//! balance_column, so the key-4 rest state is the solver's own fixed point
class Conversion {
 public:
  Conversion(int order, X1RowsCache& rows, bool const walls[2]);
  //! u: total cell averages; w: in/out primitives; trips: device counter
  void forward(torch::Tensor const& u, torch::Tensor& w,
               EquationOfStateImpl& eos, torch::Tensor& trips) const;
  //! the ghost fill with constraint c (wall4_fill today)
  void fill_walls(torch::Tensor a, int c, bool pos, torch::Tensor ref,
                  torch::Tensor rows, torch::Tensor trips) const;
};

//! x1 well-balanced reconstruction: w' = w - ref, parity ghosts, recon of
//! w', restore ref at faces with the reference fallbacks, wall mirror
class WellBalancedX1 {
 public:
  FaceStates forward(torch::Tensor const& w, ReferenceFaces const& ref,
                     class ReconstructImpl& recon) const;
};

//! one place for every face floor; acts after the last face transform of
//! a sweep (WB restore, FP32 gauge), before the Riemann solve; counts
struct FaceFloor {
  double density = 0., pressure = 0.;  // EOS floors; 0 without limiter
  bool species = false;
  void apply(FaceStates& f) const;
};

class ReconstructImpl : public torch::nn::Cloneable<ReconstructImpl> {
 public:
  ReconstructOptions options;
  ReconRows rows_mass, rows_vp;  // density+species group; v and p group
  void set_x1_faces(torch::Tensor const& x1f);
  //! w -> faces of every variable along dim; no floors (FaceFloor does it)
  FaceStates forward(torch::Tensor const& w, int dim) const;
};

}  // namespace snap
