// Multi-step questionnaire wizard (index.html only — no-ops elsewhere)
(function () {
  const form = document.getElementById("quiz-form");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll("fieldset.step"));
  const ringSteps = Array.from(document.querySelectorAll(".ring-step"));
  const btnBack = document.getElementById("btn-back");
  const btnNext = document.getElementById("btn-next");
  const btnSubmit = document.getElementById("btn-submit");

  let current = 0;

  function render() {
    steps.forEach((step, i) => {
      step.hidden = i !== current;
    });
    ringSteps.forEach((el, i) => {
      el.classList.toggle("active", i === current);
      el.classList.toggle("done", i < current);
    });
    btnBack.hidden = current === 0;
    const isLast = current === steps.length - 1;
    btnNext.hidden = isLast;
    btnSubmit.hidden = !isLast;
  }

  function currentStepValid() {
    const step = steps[current];
    const inputs = Array.from(step.querySelectorAll("input[required], select[required]"));
    for (const el of inputs) {
      if (el.type === "radio") {
        const group = step.querySelectorAll(`input[name="${el.name}"]`);
        const checked = Array.from(group).some((g) => g.checked);
        if (!checked) {
          alert("Please make a selection before continuing.");
          return false;
        }
      } else if (!el.reportValidity()) {
        return false;
      }
    }
    return true;
  }

  btnNext.addEventListener("click", () => {
    if (!currentStepValid()) return;
    current = Math.min(current + 1, steps.length - 1);
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  btnBack.addEventListener("click", () => {
    current = Math.max(current - 1, 0);
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  render();
})();