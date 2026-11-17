#pragma once
// V3 lane C skeleton (declarations only; not built). One evaluator of the
// well-balanced x1 reference for initialization (balance_column, IC
// builders) and runtime, seams included. Replaces HydroReferenceX1Operator
// (hydro_reference.hpp), HydroImpl::_hydro_ref_x1 (hydro.cpp:605-872) and
// the wb_ref4 flag/face functions. Kernel: hydro_ref_x1_impl.h, unchanged,
// instantiated for T and for SRS pairs (split_reference_scalar.hpp).

namespace snap {

//! total path: delta undefined. Split path (M3/M4): base is the FP64
//! background, delta the perturbation; every nonlinear decision reads the
//! FP64 total, arithmetic keeps the increment (finite-increment pairs)
struct ReferenceInput {
  torch::Tensor base, delta;
};

struct ReferenceFaces {
  torch::Tensor psf_lo, psf_hi, pref, dref;  // totals
  torch::Tensor dsf_lr;                      // (2, ...) per-side face rho
  torch::Tensor face0, face_delta, cell0, cell_delta, gauge;  // split only
};

//! the x1 block column a block belongs to; implemented by layout (lane O).
//! Absent (nullptr) for a single column: balance_column and nb1 = 1.
struct X1ColumnLink {
  virtual torch::Tensor take_anchor(torch::Tensor shape_like) = 0;
  virtual void pass_anchor(torch::Tensor const& face) = 0;
  //! replace ghost rows of `rows` by the neighbours' owned rows
  virtual void exchange_ghost_rows(torch::Tensor& rows, int ng) = 0;
  virtual ~X1ColumnLink() = default;
};

struct X1ReferenceConfig {
  int iu;
  bool stretched, phys_in, phys_out, wall_clamp;
  int conversion_order;  // 4 adds the face-density rows (wb_ref4)
  Scheme face_scheme;    // cp5 rows for weno5/cp5, else the kernel's dsf
};

class X1Reference {
 public:
  X1Reference(X1ReferenceConfig const& cfg, X1RowsCache& rows);
  //! one evaluation; order: kernel, anchor relay, wb_ref4 flag, ghost-row
  //! exchange, wb_ref4 faces, per-side face density (as hydro.cpp today)
  ReferenceFaces evaluate(ReferenceInput const& in, double grav,
                          X1ColumnLink* link) const;
  //! the linear signed scan (M3a), explicit anchor, no floors
  std::pair<torch::Tensor, torch::Tensor> scan_pressure(
      torch::Tensor const& rho, double grav, torch::Tensor const& anchor) const;
};

}  // namespace snap
