document.documentElement.classList.remove("no-js");
document.documentElement.classList.add("js-ready");

const frameStatus = document.querySelector("#frame-status");
const analysisForm = document.querySelector("#analysis-form");
const conversation = document.querySelector("#conversation");
const characterCount = document.querySelector("#character-count");
const analyzeButton = document.querySelector("#analyze-button");
const formMessage = document.querySelector("#form-message");
const exampleButtons = document.querySelectorAll("[data-example]");
const analysisResult = document.querySelector("#analysis-result");
const resultKicker = document.querySelector("#result-kicker");
const resultTitle = document.querySelector("#result-title");
const resultIntro = document.querySelector("#result-intro");
const resultScenario = document.querySelector("#result-scenario");
const resultJurisdiction = document.querySelector("#result-jurisdiction");
const resultVersion = document.querySelector("#result-version");
const signalsSection = document.querySelector("#signals-section");
const signalList = document.querySelector("#signal-list");
const unknownList = document.querySelector("#unknown-list");
const questionList = document.querySelector("#question-list");
const checklist = document.querySelector("#checklist");
const sourcesSection = document.querySelector("#sources-section");
const sourceList = document.querySelector("#source-list");
const limitationList = document.querySelector("#limitation-list");

const MAX_CHARACTERS = 20000;
let isSubmitting = false;
const examples = {
  job: "招聘方：线上客服每天三百，先交五百培训费才能排班，今晚不交名额就没了。",
  rental: "出租方：我在海外，不能看房，你先转一个月租金，收到钱就寄钥匙和租约。",
};

if (frameStatus) {
  frameStatus.lastChild.textContent = "核查功能已就绪";
}

const statusContent = {
  risk_signals: {
    kicker: "发现风险信号",
    title: "建议暂停付款，先完成独立核查",
    intro: "以下内容来自对话中的明确表述。它们不是诈骗认定，但值得在付款前逐项确认。",
  },
  insufficient_information: {
    kicker: "信息不足",
    title: "现有文字不足以完成核查",
    intro: "暂时没有足够信息判断付款条件和对方身份，请根据问题补充关键内容。",
  },
  no_obvious_signals: {
    kicker: "未发现明显信号",
    title: "当前文字未发现明显风险信号",
    intro: "这不代表交易绝对安全。请继续使用独立渠道核实身份、文件和收款安排。",
  },
};

const scenarioLabels = {
  auto: "场景待确认",
  job: "兼职招聘",
  rental: "租房付款",
};

function textLength(value) {
  return Array.from(value).length;
}

function updateInputState() {
  if (!conversation || !characterCount || !analyzeButton) return;

  const length = textLength(conversation.value);
  const hasText = conversation.value.trim().length > 0;
  const isTooLong = length > MAX_CHARACTERS;

  characterCount.textContent = `${length.toLocaleString("zh-Hans-CN")} / 20,000`;
  characterCount.classList.toggle("is-warning", length >= 18000);
  characterCount.classList.toggle("is-error", isTooLong);
  analyzeButton.disabled = !hasText || isTooLong || isSubmitting;
  conversation.setAttribute("aria-invalid", String(isTooLong));

  if (formMessage && formMessage.dataset.kind === "validation") {
    formMessage.textContent = "";
    delete formMessage.dataset.kind;
  }
}

conversation?.addEventListener("input", updateInputState);

exampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (!conversation) return;

    const exampleName = button.dataset.example;
    const scenarioName = button.dataset.scenario;
    conversation.value = examples[exampleName] ?? "";
    document.querySelector(`input[name="scenario"][value="${scenarioName}"]`)?.click();
    updateInputState();
    conversation.focus();
  });
});

function replaceListItems(container, items, emptyMessage = "") {
  if (!container) return;

  container.replaceChildren();
  const safeItems = Array.isArray(items) ? items : [];
  if (safeItems.length === 0 && emptyMessage) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "empty-list-item";
    emptyItem.textContent = emptyMessage;
    container.append(emptyItem);
    return;
  }

  safeItems.forEach((item) => {
    const listItem = document.createElement("li");
    listItem.textContent = item;
    container.append(listItem);
  });
}

function renderSignals(signals) {
  if (!signalList || !signalsSection) return;

  signalList.replaceChildren();
  signalsSection.hidden = signals.length === 0;
  signals.forEach((signal) => {
    const card = document.createElement("article");
    card.className = "signal-card";

    const heading = document.createElement("div");
    heading.className = "signal-heading";
    const description = document.createElement("h5");
    description.textContent = signal.description;
    const code = document.createElement("span");
    code.textContent = signal.code;
    heading.append(description, code);

    const evidenceLabel = document.createElement("strong");
    evidenceLabel.textContent = "对话原文";
    const evidence = document.createElement("blockquote");
    evidence.textContent = `“${signal.evidence_quote}”`;

    const sources = document.createElement("div");
    sources.className = "source-row";
    const sourceLabel = document.createElement("span");
    sourceLabel.textContent = "支持资料";
    sources.append(sourceLabel);
    if (signal.source_ids.length === 0) {
      const missingSource = document.createElement("em");
      missingSource.textContent = "暂无匹配来源";
      sources.append(missingSource);
    } else {
      signal.source_ids.forEach((sourceId) => {
        const source = document.createElement("code");
        source.textContent = sourceId;
        sources.append(source);
      });
    }

    card.append(heading, evidenceLabel, evidence, sources);
    signalList.append(card);
  });
}

function safeExternalUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function renderSources(sources) {
  if (!sourcesSection || !sourceList) return;

  const safeSources = Array.isArray(sources) ? sources : [];
  sourceList.replaceChildren();
  sourcesSection.hidden = safeSources.length === 0;

  safeSources.forEach((source) => {
    const card = document.createElement("article");
    card.className = "source-card";

    const heading = document.createElement("div");
    heading.className = "source-card-heading";
    const sourceId = document.createElement("span");
    sourceId.textContent = source.source_id;
    const reviewState = document.createElement("span");
    reviewState.className = "review-state";
    reviewState.textContent = source.status === "reviewed" ? "已审核" : "状态待确认";
    heading.append(sourceId, reviewState);

    const sourceUrl = safeExternalUrl(source.url);
    const title = sourceUrl
      ? document.createElement("a")
      : document.createElement("h5");
    title.className = "source-title";
    title.textContent = sourceUrl ? `${source.title} ↗` : source.title;
    if (sourceUrl && title instanceof HTMLAnchorElement) {
      title.href = sourceUrl;
      title.target = "_blank";
      title.rel = "noopener noreferrer";
      title.setAttribute("aria-label", `${source.title}（在新标签页打开官方资料）`);
    }

    const metadata = document.createElement("p");
    metadata.className = "source-metadata";
    metadata.textContent = `${source.publisher} · 发布 ${source.published_at} · 核对 ${source.checked_at}`;

    const summary = document.createElement("p");
    summary.className = "source-summary";
    summary.textContent = source.summary;

    const limits = document.createElement("p");
    limits.className = "source-limits";
    limits.textContent = `使用边界：${source.limits}`;

    card.append(heading, title, metadata, summary, limits);
    sourceList.append(card);
  });
}

function renderReport(report) {
  if (
    !analysisResult ||
    !resultKicker ||
    !resultTitle ||
    !resultIntro ||
    !resultScenario ||
    !resultJurisdiction ||
    !resultVersion
  ) {
    throw new Error("结果组件未完整载入，请刷新页面后重试。");
  }

  const content = statusContent[report.status];
  if (!content || !Array.isArray(report.signals)) {
    throw new Error("分析结果格式不完整，请稍后重试。");
  }

  analysisResult.dataset.status = report.status;
  resultKicker.textContent = content.kicker;
  resultTitle.textContent = content.title;
  resultIntro.textContent = content.intro;
  resultScenario.textContent = scenarioLabels[report.scenario] ?? report.scenario;
  resultJurisdiction.textContent = `资料地区 ${report.jurisdiction}`;
  resultVersion.textContent = report.analyzer_version;

  renderSignals(report.signals);
  renderSources(report.sources);
  replaceListItems(unknownList, report.unknowns);
  replaceListItems(questionList, report.questions);
  replaceListItems(
    checklist,
    report.checklist,
    "请先确认具体场景，再获取对应的资料核查清单。",
  );
  replaceListItems(limitationList, report.limitations);

  analysisResult.hidden = false;
  analysisResult.focus({ preventScroll: true });
  analysisResult.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setSubmitting(submitting) {
  isSubmitting = submitting;
  analysisForm?.setAttribute("aria-busy", String(submitting));
  const buttonLabel = analyzeButton?.querySelector("span");
  if (buttonLabel) {
    buttonLabel.textContent = submitting ? "正在核查…" : "开始核查";
  }
  updateInputState();
}

analysisForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!conversation || !formMessage || isSubmitting) return;

  const length = textLength(conversation.value);
  if (!conversation.value.trim()) {
    formMessage.textContent = "请先输入需要核查的对话内容。";
    formMessage.dataset.kind = "validation";
    conversation.focus();
    return;
  }
  if (length > MAX_CHARACTERS) {
    formMessage.textContent = "对话内容不能超过 20,000 个字符。";
    formMessage.dataset.kind = "validation";
    conversation.focus();
    return;
  }

  const formData = new FormData(analysisForm);
  const requestBody = {
    text: conversation.value.trim(),
    scenario: formData.get("scenario"),
    jurisdiction: formData.get("jurisdiction"),
  };

  analysisResult?.setAttribute("hidden", "");
  formMessage.textContent = "正在分析对话中的付款条件与核查信号…";
  formMessage.dataset.kind = "ready";
  setSubmitting(true);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const report = await response.json();
    if (!response.ok) {
      throw new Error(report.message || "核查请求未能完成。");
    }

    renderReport(report);
    formMessage.textContent = "核查完成，结果已显示在下方。";
    formMessage.dataset.kind = "ready";
  } catch (error) {
    formMessage.textContent =
      error instanceof Error ? error.message : "暂时无法完成核查，请稍后重试。";
    formMessage.dataset.kind = "validation";
  } finally {
    setSubmitting(false);
  }
});

updateInputState();
