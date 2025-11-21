// Auto update course target fields (total hours / weeks / hours per week)
document.addEventListener("DOMContentLoaded", () => {
  const totalField = document.getElementById("target_total_hours");
  const weeksField = document.getElementById("target_weeks");
  const perWeekField = document.getElementById("target_hours_per_week");

  if (!totalField || !weeksField || !perWeekField) {
    return;
  }

  let lastEdited = null;

  function toNumber(value) {
    const v = parseFloat(value);
    return Number.isFinite(v) ? v : null;
  }

  function updateFields() {
    const total = toNumber(totalField.value);
    const weeks = toNumber(weeksField.value);
    const perWeek = toNumber(perWeekField.value);

    if (lastEdited === "total") {
      if (weeks !== null && weeks > 0) {
        const computed = total !== null ? total / weeks : null;
        perWeekField.value = computed !== null ? computed.toFixed(1) : "";
      }
    } else if (lastEdited === "weeks") {
      if (total !== null && weeks > 0) {
        const computed = total / weeks;
        perWeekField.value = computed.toFixed(1);
      } else if (perWeek !== null) {
        const computed = weeks !== null ? weeks * perWeek : null;
        totalField.value = computed !== null ? computed.toFixed(1) : "";
      }
    } else if (lastEdited === "perWeek") {
      if (weeks !== null) {
        const computed = weeks * perWeek;
        totalField.value = computed.toFixed(1);
      } else if (total !== null && perWeek > 0) {
        const computed = total / perWeek;
        weeksField.value = Math.round(computed);
      }
    }
  }

  totalField.addEventListener("input", () => {
    lastEdited = "total";
    updateFields();
  });

  weeksField.addEventListener("input", () => {
    lastEdited = "weeks";
    updateFields();
  });

  perWeekField.addEventListener("input", () => {
    lastEdited = "perWeek";
    updateFields();
  });
});

// Animate course progress bars on the summary page
document.addEventListener("DOMContentLoaded", () => {
  const bars = document.querySelectorAll(".progress-bar[data-progress]");

  bars.forEach((bar) => {
    const target = parseFloat(bar.getAttribute("data-progress"));
    if (!Number.isFinite(target)) {
      return;
    }

    // Smooth animation for width
    if (!bar.style.transition) {
      bar.style.transition = "width 600ms ease-out";
    }

    // Let layout settle, then animate to target width
    requestAnimationFrame(() => {
      bar.style.width = `${Math.min(target, 100)}%`;
    });
  });
});
