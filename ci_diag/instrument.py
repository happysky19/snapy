"""Instrument disposable CI checkouts of the existing seam test."""

from pathlib import Path
import sys

OLD = """  for (int n = 0; n < nstep; ++n) {
    step(one, v1, dt);
    step(two, v2, dt);
    ep_max = std::max(ep_max, std::abs(energy_p(two, v2) - ep0) / ep0);
  }
"""

NEW = """  bool reported = false;
  auto probe = [&](int stepno) {
    if (reported) return;
    auto a = column_state(one, v1), c = column_state(two, v2);
    for (int var : {IDN, IVX, IPR}) {
      auto av = a[var].reshape({-1}).contiguous();
      auto cv = c[var].reshape({-1}).contiguous();
      auto ap = av.data_ptr<double>(), cp = cv.data_ptr<double>();
      for (int64_t i = 0; i < av.numel(); ++i) {
        if (ap[i] != cp[i]) {
          std::printf("FIRST nx1=%d step=%d field=%s cell=%lld one=%.17g two=%.17g\\n",
                      nx1, stepno, var == IDN ? "rho" : var == IVX ? "rho_v1" : "E",
                      static_cast<long long>(i), ap[i], cp[i]);
          reported = true;
          return;
        }
      }
    }
  };
  probe(0);
  for (int n = 0; n < nstep; ++n) {
    step(one, v1, dt);
    step(two, v2, dt);
    probe(n + 1);
    ep_max = std::max(ep_max, std::abs(energy_p(two, v2) - ep0) / ep0);
  }
  if (!reported) std::printf("FIRST nx1=%d none through step=%d\\n", nx1, nstep);
"""

for name in sys.argv[1:]:
    path = Path(name) / "tests/test_x1_seam_split.cpp"
    source = path.read_text()
    if source.count(OLD) != 1:
        raise RuntimeError(f"expected one target loop in {path}")
    path.write_text(source.replace(OLD, NEW))
    print(f"instrumented {path}")
