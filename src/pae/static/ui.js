(() => {
  const panels = [...document.querySelectorAll("[data-step]")];
  const links = [...document.querySelectorAll("[data-step-target]")];
  const progressBar = document.querySelector("#progress-bar");
  const progressText = document.querySelector("#progress-text");
  const toast = document.querySelector("#toast");
  let currentStep = 1;

  function showStep(step) {
    currentStep = Math.max(1, Math.min(10, Number(step)));
    panels.forEach((panel) => panel.classList.toggle("active", Number(panel.dataset.step) === currentStep));
    links.forEach((link) => {
      const linkStep = Number(link.dataset.stepTarget);
      link.classList.toggle("active", linkStep === currentStep);
      link.classList.toggle("complete", linkStep < currentStep);
    });
    progressBar.style.width = `${currentStep * 10}%`;
    progressText.textContent = `${currentStep} / 10`;
    document.querySelector("main").scrollTo({ top: 0, behavior: "smooth" });
    window.history.replaceState(null, "", `#step-${currentStep}`);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("visible");
    window.setTimeout(() => toast.classList.remove("visible"), 2400);
  }

  links.forEach((link) => link.addEventListener("click", () => showStep(link.dataset.stepTarget)));
  document.querySelectorAll("[data-next]").forEach((button) => button.addEventListener("click", () => showStep(currentStep + 1)));
  document.querySelectorAll("[data-back]").forEach((button) => button.addEventListener("click", () => showStep(currentStep - 1)));
  document.querySelectorAll("[data-go-first]").forEach((button) => button.addEventListener("click", () => showStep(1)));
  document.querySelectorAll("[data-toast]").forEach((button) => button.addEventListener("click", () => showToast(button.dataset.toast)));

  document.querySelector("[data-analyze]").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = "กำลังอ่าน header และ sample…";
    window.setTimeout(() => {
      button.disabled = false;
      button.innerHTML = original;
      showStep(3);
      showToast("วิเคราะห์เสร็จแล้ว: พบ 6 columns และมีคำแนะนำพร้อมเหตุผล");
    }, 650);
  });

  const fileInput = document.querySelector("#source-file");
  fileInput.addEventListener("change", () => {
    const name = fileInput.files[0]?.name;
    if (name) document.querySelector("#file-label").textContent = `${name} · Prototype จะไม่อ่านหรือส่งไฟล์นี้`;
  });

  document.querySelectorAll(".language-card input").forEach((input) => input.addEventListener("change", () => {
    document.querySelectorAll(".language-card").forEach((card) => card.classList.remove("selected"));
    input.closest(".language-card").classList.add("selected");
  }));

  document.querySelectorAll("[data-code-tab]").forEach((tab) => tab.addEventListener("click", () => {
    const selected = tab.dataset.codeTab;
    document.querySelectorAll("[data-code-tab]").forEach((item) => item.classList.toggle("active", item === tab));
    document.querySelectorAll("[data-code-content]").forEach((content) => { content.hidden = content.dataset.codeContent !== selected; });
  }));

  document.querySelector("[data-copy]").addEventListener("click", async () => {
    const content = document.querySelector("[data-code-content]:not([hidden])").textContent;
    await navigator.clipboard.writeText(content);
    showToast("คัดลอกแล้ว");
  });

  const jobState = document.querySelector("#job-state");
  const jobMessage = document.querySelector("#job-message");
  const jobProgress = document.querySelector("#job-progress-bar");
  const jobRun = document.querySelector("#job-run");
  const jobCancel = document.querySelector("#job-cancel");
  const jobRetry = document.querySelector("#job-retry");
  let jobTimer;

  function resetJob() {
    window.clearInterval(jobTimer);
    jobProgress.style.width = "0%";
    jobState.textContent = "Idle";
    jobState.className = "status-pill draft";
    jobMessage.textContent = "พร้อมจำลองการสร้างและตรวจ package";
    jobRun.disabled = false;
    jobCancel.disabled = true;
    jobRetry.hidden = true;
  }

  function runJob() {
    let progress = 0;
    window.clearInterval(jobTimer);
    jobState.textContent = "Running";
    jobState.className = "status-pill warning";
    jobMessage.textContent = "กำลังสร้าง mock artifact และตรวจ policy…";
    jobRun.disabled = true;
    jobCancel.disabled = false;
    jobRetry.hidden = true;
    jobTimer = window.setInterval(() => {
      progress += 10;
      jobProgress.style.width = `${progress}%`;
      if (progress >= 100) {
        window.clearInterval(jobTimer);
        jobState.textContent = "Completed";
        jobState.className = "status-pill ready";
        jobMessage.textContent = "Mock job เสร็จแล้ว — ไม่มีการ execute generated code จริง";
        jobCancel.disabled = true;
        jobRetry.hidden = false;
      }
    }, 90);
  }

  jobRun.addEventListener("click", runJob);
  jobRetry.addEventListener("click", runJob);
  jobCancel.addEventListener("click", () => {
    window.clearInterval(jobTimer);
    jobState.textContent = "Cancelled";
    jobState.className = "status-pill mock";
    jobMessage.textContent = "ยกเลิก mock job แล้ว สามารถลองใหม่ได้";
    jobCancel.disabled = true;
    jobRetry.hidden = false;
  });
  resetJob();

  const initialStep = Number(window.location.hash.replace("#step-", "")) || 1;
  showStep(initialStep);
})();
