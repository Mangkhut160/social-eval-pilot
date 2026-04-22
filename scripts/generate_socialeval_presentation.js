let PptxGenJS;
try {
  PptxGenJS = require("pptxgenjs");
} catch {
  PptxGenJS = require("/tmp/socialeval-ppt/node_modules/pptxgenjs");
}

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "OpenAI Codex";
pptx.company = "SocialEval";
pptx.subject = "AI-assisted academic evaluation system";
pptx.title = "面向自主知识体系的 AI 辅助学术评价系统";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  lang: "zh-CN",
};

const W = 13.333;
const H = 7.5;
const C = {
  primary: "C8161E",
  primarySoft: "E96E73",
  accentBlue: "1F4D78",
  accentSlate: "44546A",
  ink: "333333",
  slate: "667085",
  white: "FFFFFF",
  mist: "F7F7F7",
  snow: "FBFBFC",
  pale: "F2F2F2",
  line: "D9D9D9",
  lineDark: "BFBFBF",
  navy: "44546A",
  navy2: "5D7088",
  sand: "F7F7F7",
  sand2: "EFEFEF",
  bronze: "C8161E",
  teal: "1F4D78",
  sage: "F4F6F8",
  rose: "FAF3F3",
  red: "C8161E",
  gold: "C8161E",
};

const A = {
  bg: "docs/presentations/template-assets/image5.png",
  motif: "docs/presentations/template-assets/image2.png",
  motto: "docs/presentations/template-assets/image3.png",
  logo: "docs/presentations/template-assets/image4.png",
  gateWide: "docs/presentations/template-assets/image1.png",
  gate: "docs/presentations/template-assets/image6.png",
  seal: "docs/presentations/template-assets/image7.png",
  aiText: "docs/presentations/template-assets/image8.png",
};

function addPageNumber(slide, n, dark = false) {
  slide.addText(String(n).padStart(2, "0"), {
    x: 0.88,
    y: 0.38,
    w: 0.42,
    h: 0.18,
    fontFace: "Calibri",
    fontSize: 12,
    bold: true,
    color: dark ? C.white : C.primary,
    align: "left",
    margin: 0,
  });
}

function addBrandHeader(slide, showLeftLogo = true) {
  if (showLeftLogo) {
    slide.addImage({
      path: A.logo,
      x: 0.72,
      y: 0.22,
      w: 2.0,
      h: 0.23,
    });
  }
  slide.addImage({
    path: A.motif,
    x: 9.72,
    y: 0.2,
    w: 2.7,
    h: 0.09,
  });
}

function addFooterMotto(slide) {
  slide.addShape(pptx.ShapeType.line, {
    x: 0.72,
    y: 7.06,
    w: 2.8,
    h: 0,
    line: { color: C.line, width: 1 },
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 9.8,
    y: 7.06,
    w: 2.8,
    h: 0,
    line: { color: C.line, width: 1 },
  });
  slide.addImage({
    path: A.motto,
    x: 3.5,
    y: 6.82,
    w: 6.35,
    h: 0.22,
    transparency: 30,
  });
}

function addLightFrame(slide, n, section) {
  slide.background = { path: A.bg };
  addBrandHeader(slide, true);
  addPageNumber(slide, n, false);
  slide.addText(section, {
    x: 1.18,
    y: 0.38,
    w: 1.8,
    h: 0.18,
    fontSize: 11,
    bold: true,
    color: C.accentSlate,
    margin: 0,
    charSpacing: 1.2,
  });
  slide.addText("SocialEval", {
    x: 11.0,
    y: 0.38,
    w: 1.0,
    h: 0.15,
    fontFace: "Calibri",
    fontSize: 9,
    color: C.slate,
    italic: true,
    align: "left",
    margin: 0,
  });
  addFooterMotto(slide);
}

function addDarkFrame(slide, n) {
  slide.background = { color: C.accentSlate };
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: W,
    h: H,
    fill: { color: C.accentSlate },
    line: { color: C.accentSlate, transparency: 100 },
  });
  addPageNumber(slide, n, true);
}

function addTitle(slide, title, subtitle, opts = {}) {
  const x = opts.x ?? 0.85;
  const y = opts.y ?? 0.75;
  const w = opts.w ?? 7.1;
  const dark = opts.dark ?? false;
  slide.addText(title, {
    x,
    y,
    w,
    h: opts.hTitle ?? 0.72,
    fontSize: opts.titleSize ?? 24,
    bold: true,
    color: dark ? C.white : C.primary,
    margin: 0,
  });
  slide.addText(subtitle, {
    x,
    y: y + 0.56,
    w,
    h: opts.hSubtitle ?? 0.34,
    fontFace: "Calibri",
    fontSize: opts.subtitleSize ?? 10.5,
    color: dark ? "D9E6EF" : C.slate,
    italic: true,
    margin: 0,
  });
  if (!dark) {
    slide.addShape(pptx.ShapeType.line, {
      x,
      y: y + 0.98,
      w: Math.min(w, 8.8),
      h: 0,
      line: { color: C.lineDark, width: 1.1 },
    });
  }
}

function addBullets(slide, items, opts = {}) {
  const runs = [];
  items.forEach((item, i) => {
    runs.push({
      text: item,
      options: {
        bullet: { indent: opts.indent ?? 14 },
        hanging: 2,
        breakLine: i < items.length - 1,
      },
    });
  });
  slide.addText(runs, {
    x: opts.x ?? 0.95,
    y: opts.y ?? 1.7,
    w: opts.w ?? 5.2,
    h: opts.h ?? 3.6,
    fontSize: opts.fontSize ?? 17,
    color: opts.color ?? C.ink,
    breakLine: true,
    paraSpaceAfterPt: opts.spaceAfter ?? 12,
    valign: "top",
    margin: 0.03,
    fit: "shrink",
  });
}

function addCard(slide, x, y, w, h, options = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.07,
    fill: { color: options.fill || C.white, transparency: options.transparency || 0 },
    line: { color: options.line || C.line, width: options.lineWidth || 1 },
    shadow: options.shadow
      ? { type: "outer", color: "000000", blur: 1, offset: 1, angle: 45, opacity: 0.12 }
      : undefined,
  });
}

function addLabel(slide, text, x, y, w, color, fill) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h: 0.34,
    rectRadius: 0.07,
    fill: { color: fill },
    line: { color: fill, transparency: 100 },
  });
  slide.addText(text, {
    x,
    y: y + 0.07,
    w,
    h: 0.15,
    fontSize: 9.5,
    bold: true,
    color,
    align: "center",
    margin: 0,
  });
}

function addStat(slide, x, y, w, h, number, label, tone) {
  addCard(slide, x, y, w, h, { fill: C.white, line: C.line });
  slide.addText(number, {
    x: x + 0.18,
    y: y + 0.18,
    w: w - 0.36,
    h: 0.45,
    fontFace: "Calibri",
    fontSize: 25,
    bold: true,
    color: tone,
    margin: 0,
    align: "center",
  });
  slide.addText(label, {
    x: x + 0.18,
    y: y + 0.72,
    w: w - 0.36,
    h: 0.35,
    fontSize: 10.5,
    color: C.slate,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
}

function addChevron(slide, x, y, text, fill, color = C.white) {
  slide.addShape(pptx.ShapeType.chevron, {
    x,
    y,
    w: 1.55,
    h: 0.7,
    fill: { color: fill },
    line: { color: fill, transparency: 100 },
  });
  slide.addText(text, {
    x: x + 0.12,
    y: y + 0.18,
    w: 1.18,
    h: 0.18,
    fontSize: 10.5,
    bold: true,
    color,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
}

function addMiniBulletList(slide, items, x, y, w, h, color = C.ink) {
  const runs = [];
  items.forEach((item, i) => {
    runs.push({
      text: item,
      options: {
        bullet: { indent: 10 },
        hanging: 2,
        breakLine: i < items.length - 1,
      },
    });
  });
  slide.addText(runs, {
    x,
    y,
    w,
    h,
    fontSize: 11,
    color,
    paraSpaceAfterPt: 8,
    margin: 0,
    fit: "shrink",
  });
}

function addFooterNote(slide, text, dark = false) {
  slide.addText(text, {
    x: 0.9,
    y: 6.54,
    w: 10.2,
    h: 0.18,
    fontSize: 9,
    color: dark ? "D5E0E8" : C.slate,
    italic: true,
    margin: 0,
    fit: "shrink",
  });
}

function addSlide1() {
  const slide = pptx.addSlide();
  slide.background = { path: A.bg };
  addBrandHeader(slide, true);
  slide.addShape(pptx.ShapeType.line, {
    x: 2.25,
    y: 1.9,
    w: 8.9,
    h: 0,
    line: { color: C.lineDark, width: 1.2 },
  });
  slide.addText("面向自主知识体系的\nAI 辅助学术评价系统", {
    x: 2.05,
    y: 2.25,
    w: 9.25,
    h: 0.95,
    fontSize: 31,
    bold: true,
    color: C.primary,
    align: "center",
    margin: 0,
    breakLine: true,
    fit: "shrink",
  });
  slide.addText("AI-Assisted Academic Evaluation System for Indigenous Knowledge Frameworks", {
    x: 2.0,
    y: 3.5,
    w: 9.35,
    h: 0.22,
    fontFace: "Calibri",
    fontSize: 13.5,
    color: C.accentSlate,
    italic: true,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  slide.addText("以法学论文评审为切入点，构建可信、可解释、可扩展的人文社科评价基础设施", {
    x: 2.15,
    y: 4.25,
    w: 9.0,
    h: 0.35,
    fontSize: 16,
    color: C.accentSlate,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  slide.addImage({
    path: A.gateWide,
    x: 1.15,
    y: 4.6,
    w: 11.15,
    h: 2.65,
    transparency: 0,
  });
  slide.addText("SocialEval\n2026.03", {
    x: 5.45,
    y: 5.4,
    w: 2.4,
    h: 0.42,
    fontFace: "Calibri",
    fontSize: 13,
    bold: true,
    color: C.accentSlate,
    align: "center",
    margin: 0,
  });
  addFooterMotto(slide);
}

function addSlide2() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 2, "BACKGROUND");
  addTitle(slide, "学术评价为何需要新的技术支撑", "Why Academic Evaluation Needs New Technical Support");
  addBullets(slide, [
    "传统学术评价长期面临标准不一、效率偏低、专家成本高的结构性张力。",
    "人文社科尤其依赖隐性知识、学科语境与资深判断，难以完全流程化。",
    "稿件数量增长与评审资源有限并存，初审阶段的时间压力持续上升。",
    "需要一种提升效率、保留学科判断、并支持追溯的辅助机制。",
  ], { x: 0.95, y: 1.75, w: 5.3, h: 4.3, fontSize: 16.5 });
  slide.addShape(pptx.ShapeType.triangle, {
    x: 7.4,
    y: 2.0,
    w: 4.5,
    h: 3.6,
    rotate: 180,
    fill: { color: C.mist },
    line: { color: "BFCED9", width: 1.2 },
  });
  [
    ["标准统一", 8.95, 1.55, C.navy],
    ["评审效率", 7.0, 4.75, C.teal],
    ["专家成本", 10.7, 4.75, C.red],
  ].forEach(([t, x, y, fill]) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x,
      y,
      w: 1.25,
      h: 1.25,
      fill: { color: fill },
      line: { color: fill, transparency: 100 },
    });
    slide.addText(t, {
      x,
      y: y + 0.44,
      w: 1.25,
      h: 0.2,
      fontSize: 11,
      bold: true,
      color: C.white,
      align: "center",
      margin: 0,
    });
  });
  addCard(slide, 7.35, 5.85, 4.9, 0.72, { fill: C.white, line: C.line });
  slide.addText("评价质量的提升，取决于把“标准、效率、成本”的三角冲突转化为可设计的系统机制。", {
    x: 7.62,
    y: 6.06,
    w: 4.35,
    h: 0.28,
    fontSize: 11.2,
    color: C.ink,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
}

function addSlide3() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 3, "CHALLENGE");
  addTitle(slide, "为什么不能用“通用 AI 打分”替代学术评价", "Why Generic AI Scoring Is Not Enough");
  addCard(slide, 0.95, 1.95, 5.35, 4.65, { fill: C.white, line: C.line, shadow: true });
  addCard(slide, 7.0, 1.95, 5.35, 4.65, { fill: C.mist, line: "BFD1DF", shadow: true });
  addLabel(slide, "Generic AI", 1.2, 2.2, 1.35, C.white, C.red);
  addLabel(slide, "Scholarly Evaluation", 7.25, 2.2, 2.0, C.white, C.teal);
  const leftRows = ["语言流畅度", "常识性总结", "形式特征识别", "表面相关性"];
  const rightRows = ["问题意识判断", "文献位置辨认", "理论建构评估", "论证链条审查"];
  leftRows.forEach((t, i) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x: 1.2,
      y: 2.85 + i * 0.8,
      w: 4.55,
      h: 0.52,
      rectRadius: 0.06,
      fill: { color: "FAF0EE" },
      line: { color: "E9C7C3", width: 1 },
    });
    slide.addText(t, {
      x: 1.42,
      y: 3.03 + i * 0.8,
      w: 4.0,
      h: 0.14,
      fontSize: 14,
      color: C.ink,
      margin: 0,
    });
  });
  rightRows.forEach((t, i) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x: 7.25,
      y: 2.85 + i * 0.8,
      w: 4.55,
      h: 0.52,
      rectRadius: 0.06,
      fill: { color: "EFF7F5" },
      line: { color: "B6D3CF", width: 1 },
    });
    slide.addText(t, {
      x: 7.47,
      y: 3.03 + i * 0.8,
      w: 4.0,
      h: 0.14,
      fontSize: 14,
      color: C.ink,
      margin: 0,
    });
  });
  addFooterNote(slide, "关键不只是接入模型，而是先定义评价标准，避免“像论文”被误判为“高质量论文”。");
}

function addSlide4() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 4, "FOUNDATION");
  addTitle(slide, "“自主知识体系”作为评价底层逻辑", "Indigenous Knowledge Framework as Evaluation Foundation");
  addBullets(slide, [
    "评价标准来自学科自身的问题意识、理论传统与学术共同体实践。",
    "知识体系不是装饰性概念，而是评价维度、提示词设计与解释输出的上位约束。",
    "通过外部化配置，系统避免把评价标准隐含在代码与模型习惯之中。",
    "AI 输出因此从“模型意见”转向“知识体系约束下的结构化判断”。",
  ], { x: 0.95, y: 1.8, w: 5.2, h: 4.4, fontSize: 16.2 });
  const layers = [
    ["知识体系层", "学科问题意识 / 理论传统 / 学术共同体", 7.05, 2.15, 5.1, 0.92, C.navy, C.white],
    ["评价框架层", "维度定义 / 权重 / 阈值 / 提示词模板", 7.55, 3.18, 4.6, 0.92, C.bronze, C.white],
    ["AI 执行层", "逐维提示 / 结构化输出 / 证据引用 / 审计记录", 8.0, 4.21, 4.15, 0.92, C.teal, C.white],
  ];
  layers.forEach(([title, body, x, y, w, h, fill, color]) => {
    addCard(slide, x, y, w, h, { fill, line: fill, shadow: true });
    slide.addText(title, {
      x: x + 0.22,
      y: y + 0.15,
      w: w - 0.44,
      h: 0.22,
      fontSize: 14,
      bold: true,
      color,
      margin: 0,
    });
    slide.addText(body, {
      x: x + 0.22,
      y: y + 0.43,
      w: w - 0.44,
      h: 0.18,
      fontSize: 10.5,
      color: color,
      margin: 0,
      fit: "shrink",
    });
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 9.55,
    y: 3.05,
    w: 0,
    h: 1.0,
    line: { color: "AEBECD", width: 1.2, endArrowType: "triangle" },
  });
}

function addSlide5() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 5, "FRAMEWORK");
  addTitle(slide, "法学论文的六维评价框架", "Six-Dimension Evaluation Framework for Legal Scholarship");
  const cards = [
    ["问题创新性", "Problem Originality", "研究问题的独创性与价值", C.navy],
    ["现状洞察度", "Literature Insight", "对既有研究的把握与批判", C.teal],
    ["理论建构力", "Theoretical Construction", "理论框架的完整性与自洽性", C.bronze],
    ["逻辑严密性", "Logical Coherence", "论证推理的严谨程度", C.red],
    ["学术共识度", "Scholarly Consensus", "与主流学术共同体的对话程度", "6A5B8C"],
    ["前瞻延展性", "Forward Extension", "对未来议题的开拓潜力", "546A7B"],
  ];
  cards.forEach((card, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.95 + col * 4.05;
    const y = 1.95 + row * 2.0;
    addCard(slide, x, y, 3.45, 1.55, { fill: C.white, line: C.line, shadow: true });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: x + 0.22,
      y: y + 0.22,
      w: 0.38,
      h: 0.38,
      fill: { color: card[3] },
      line: { color: card[3], transparency: 100 },
    });
    slide.addText(card[0], {
      x: x + 0.7,
      y: y + 0.2,
      w: 2.45,
      h: 0.22,
      fontSize: 14,
      bold: true,
      color: C.ink,
      margin: 0,
    });
    slide.addText(card[1], {
      x: x + 0.7,
      y: y + 0.48,
      w: 2.4,
      h: 0.16,
      fontFace: "Calibri",
      fontSize: 9.5,
      color: C.slate,
      italic: true,
      margin: 0,
      fit: "shrink",
    });
    slide.addText(card[2], {
      x: x + 0.22,
      y: y + 0.86,
      w: 3.0,
      h: 0.4,
      fontSize: 11.2,
      color: C.ink,
      margin: 0,
      fit: "shrink",
    });
  });
  addFooterNote(slide, "六维框架既是法学默认配置，也构成后续多学科扩展时的抽象模板。");
}

function addSlide6() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 6, "WORKFLOW");
  addTitle(slide, "系统总体机制：从论文输入到标准化报告", "End-to-End System Workflow");
  const steps = [
    ["论文输入", C.navy],
    ["文档预处理", C.teal],
    ["框架加载", C.bronze],
    ["AI 逐维评价", C.red],
    ["可靠性验证", "6A5B8C"],
    ["报告与复核", "546A7B"],
  ];
  steps.forEach((step, i) => addChevron(slide, 0.95 + i * 1.95, 2.45, step[0], step[1]));
  slide.addText("结构化流程编排，而不是单次模型调用。", {
    x: 0.98,
    y: 1.62,
    w: 5.0,
    h: 0.18,
    fontSize: 15,
    color: C.ink,
    bold: true,
    margin: 0,
  });
  addBullets(slide, [
    "多模型并发与一致性验证共同承担可信性保障。",
    "专家复核只在分歧处聚焦介入，形成人机协同闭环。",
    "报告输出保留标准化结果，也保留可追溯的过程信息。",
  ], { x: 0.98, y: 4.0, w: 5.35, h: 2.2, fontSize: 15.2 });
  addCard(slide, 7.35, 4.0, 4.95, 1.85, { fill: C.white, line: C.line, shadow: true });
  slide.addText("可信机制的核心不是“更强模型”，而是：\n可定义的标准 + 可观察的分歧 + 可介入的专家判断", {
    x: 7.68,
    y: 4.45,
    w: 4.25,
    h: 0.78,
    fontSize: 15,
    bold: true,
    color: C.navy,
    margin: 0,
    align: "center",
    breakLine: true,
    fit: "shrink",
  });
}

function addSlide7() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 7, "INGESTION");
  addTitle(slide, "文档摄取与预处理：把论文变成可评价对象", "Ingestion and Preprocessing");
  addCard(slide, 0.95, 1.9, 3.1, 3.9, { fill: C.white, line: C.line, shadow: true });
  slide.addText("原始论文", {
    x: 1.25, y: 2.18, w: 1.2, h: 0.16, fontSize: 13, bold: true, color: C.navy, margin: 0,
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 1.22, y: 2.55, w: 2.55, h: 2.8, fill: { color: C.mist }, line: { color: "BFD1DF", width: 1 },
  });
  ["页眉", "摘要", "引言", "主体内容", "参考文献"].forEach((t, i) => {
    slide.addText(t, {
      x: 1.45, y: 2.82 + i * 0.46, w: 1.6, h: 0.14, fontSize: 11, color: i === 0 || i === 4 ? C.red : C.ink, margin: 0,
    });
    slide.addShape(pptx.ShapeType.line, {
      x: 1.38, y: 2.98 + i * 0.46, w: 1.95, h: 0, line: { color: C.line, width: 0.6 },
    });
  });
  slide.addShape(pptx.ShapeType.chevron, {
    x: 4.3, y: 3.2, w: 1.25, h: 0.7, fill: { color: C.bronze }, line: { color: C.bronze, transparency: 100 },
  });
  addCard(slide, 5.8, 1.9, 3.1, 3.9, { fill: C.white, line: C.line, shadow: true });
  slide.addText("结构化文本", {
    x: 6.08, y: 2.18, w: 1.5, h: 0.16, fontSize: 13, bold: true, color: C.teal, margin: 0,
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 6.08, y: 2.55, w: 2.55, h: 2.8, fill: { color: "F7FBFA" }, line: { color: "BCD6D3", width: 1 },
  });
  ["摘要", "引言", "主体", "结论", "参考文献(独立字段)"].forEach((t, i) => {
    slide.addText(t, {
      x: 6.32, y: 2.82 + i * 0.46, w: 1.95, h: 0.14, fontSize: 11, color: i === 4 ? C.bronze : C.ink, margin: 0,
    });
    slide.addShape(pptx.ShapeType.line, {
      x: 6.25, y: 2.98 + i * 0.46, w: 1.98, h: 0, line: { color: C.line, width: 0.6 },
    });
  });
  addBullets(slide, [
    "支持 PDF、DOCX、TXT 等常见学术文稿格式。",
    "自动去除页眉页脚、致谢等评价噪声，同时独立提取参考文献。",
    "结构识别失败时降级为全文分段模式，并在报告中留痕。",
    "v1 默认不支持扫描版 PDF OCR，以保证输入质量。",
  ], { x: 9.35, y: 1.95, w: 3.0, h: 3.95, fontSize: 13.5 });
  addStat(slide, 0.98, 6.0, 1.85, 0.85, "PDF", "文本型优先", C.navy);
  addStat(slide, 2.98, 6.0, 1.85, 0.85, "DOCX", "结构友好", C.teal);
  addStat(slide, 4.98, 6.0, 1.85, 0.85, "TXT", "降级兼容", C.bronze);
}

function addSlide8() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 8, "ENGINE");
  addTitle(slide, "AI 评价引擎：按维度生成结构化判断", "Dimension-Level AI Evaluation Engine");
  addCard(slide, 0.95, 1.95, 5.35, 4.55, { fill: C.white, line: C.line, shadow: true });
  addLabel(slide, "Structured JSON", 1.22, 2.18, 1.6, C.white, C.navy);
  slide.addShape(pptx.ShapeType.rect, {
    x: 1.2, y: 2.6, w: 4.82, h: 3.55, fill: { color: "243949" }, line: { color: "243949", transparency: 100 },
  });
  slide.addText('{\n  "dimension": "问题创新性",\n  "score": 82,\n  "evidence_quotes": [\n    "论文原文引用片段 1",\n    "论文原文引用片段 2"\n  ],\n  "analysis": "AI 分析说明文本"\n}', {
    x: 1.45,
    y: 2.88,
    w: 4.25,
    h: 2.9,
    fontFace: "Courier New",
    fontSize: 13,
    color: C.white,
    margin: 0,
    breakLine: true,
    fit: "shrink",
  });
  addCard(slide, 7.05, 2.05, 5.2, 1.0, { fill: C.mist, line: "BFD1DF" });
  addCard(slide, 7.05, 3.25, 5.2, 1.0, { fill: "F7FBFA", line: "BCD6D3" });
  addCard(slide, 7.05, 4.45, 5.2, 1.0, { fill: "FBF6EF", line: "DCCBAE" });
  [
    ["逐维提示构造", "每个评价维度单独形成 prompt，而不是让模型直接给总分。", C.navy, 2.3],
    ["统一 Provider 抽象", "业务层不直接绑定 SDK，便于切换 OpenAI / Anthropic / DeepSeek。", C.teal, 3.5],
    ["审计友好输出", "分数、证据引用、分析说明都以结构化字段沉淀，便于追溯。", C.bronze, 4.7],
  ].forEach(([title, body, color, y]) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 7.3, y: y + 0.05, w: 0.28, h: 0.28, fill: { color }, line: { color, transparency: 100 },
    });
    slide.addText(title, {
      x: 7.68, y, w: 1.8, h: 0.18, fontSize: 13.2, bold: true, color: C.ink, margin: 0,
    });
     slide.addText(body, {
      x: 9.08, y: y - 0.02, w: 2.82, h: 0.26, fontSize: 10.6, color: C.slate, margin: 0, fit: "shrink",
      });
  });
}

function addSlide9() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 9, "CONCURRENCY");
  addTitle(slide, "多模型并发：不是堆模型，而是观察稳定性", "Multi-Model Concurrency for Stability, Not Hype");
  addBullets(slide, [
    "同一论文、同一维度可并发提交给多个模型，收集不同模型评分结果。",
    "重点不在“谁更聪明”，而在于观察不同模型对同一学术判断是否趋同。",
    "v1 默认并发数为 3，上限为 5，在成本与可靠性之间做平衡。",
  ], { x: 0.95, y: 1.88, w: 4.8, h: 2.55, fontSize: 15.2 });
  addCard(slide, 5.95, 1.95, 6.2, 4.45, { fill: C.white, line: C.line, shadow: true });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 8.3, y: 2.35, w: 1.55, h: 0.82, rectRadius: 0.06, fill: { color: C.navy }, line: { color: C.navy, transparency: 100 },
  });
  slide.addText("同一篇论文\n同一评价维度", {
    x: 8.42, y: 2.53, w: 1.3, h: 0.3, fontSize: 12.5, bold: true, color: C.white, align: "center", margin: 0, fit: "shrink",
  });
  const models = [
    ["Model A", 6.55, 3.7, C.navy],
    ["Model B", 8.45, 3.7, C.teal],
    ["Model C", 10.35, 3.7, C.bronze],
  ];
  models.forEach(([name, x, y, color]) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x, y, w: 1.25, h: 0.72, rectRadius: 0.05, fill: { color }, line: { color, transparency: 100 },
    });
    slide.addText(name, {
      x, y: y + 0.25, w: 1.25, h: 0.15, fontFace: "Calibri", fontSize: 12, bold: true, color: C.white, align: "center", margin: 0,
    });
    slide.addShape(pptx.ShapeType.line, {
      x: 9.05, y: 3.17, w: x + 0.62 - 9.05, h: 0.53, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
    });
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 7.18, y: 4.42, w: 1.9, h: 0.86, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 9.08, y: 4.42, w: 0, h: 0.86, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 10.98, y: 4.42, w: -1.9, h: 0.86, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.78, y: 5.32, w: 2.58, h: 0.84, rectRadius: 0.06, fill: { color: "EEF6F3" }, line: { color: "BCD6D3", width: 1 },
  });
  slide.addText("评分集合 / divergence → convergence", {
    x: 8.0, y: 5.62, w: 2.15, h: 0.15, fontFace: "Calibri", fontSize: 11.2, bold: true, color: C.teal, align: "center", margin: 0, fit: "shrink",
  });
  addStat(slide, 1.0, 5.1, 1.7, 0.9, "3", "默认并发数", C.navy);
  addStat(slide, 2.9, 5.1, 1.7, 0.9, "5", "并发上限", C.bronze);
}

function addSlide10() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 10, "RELIABILITY");
  addTitle(slide, "可靠性验证：把“模型结果”转化为“可信结果”", "Reliability Validation Layer");
  addCard(slide, 0.95, 1.98, 3.15, 4.55, { fill: C.white, line: C.line, shadow: true });
  slide.addText("Std ≤ 5", {
    x: 1.28, y: 2.55, w: 2.45, h: 0.52, fontFace: "Calibri", fontSize: 30, bold: true, color: C.navy, align: "center", margin: 0,
  });
  slide.addText("高置信度阈值", {
    x: 1.5, y: 3.15, w: 2.0, h: 0.18, fontSize: 14, bold: true, color: C.ink, align: "center", margin: 0,
  });
  slide.addText("均值与标准差让结果不仅是“一个分数”，而是“分数 + 分歧程度 + 置信标签”。", {
    x: 1.28, y: 3.72, w: 2.5, h: 0.9, fontSize: 12.2, color: C.slate, align: "center", margin: 0, fit: "shrink",
  });
  addLabel(slide, "High Confidence", 1.48, 5.32, 1.95, C.white, C.teal);
  addCard(slide, 4.55, 1.98, 7.7, 4.55, { fill: C.white, line: C.line, shadow: true });
  slide.addText("示例：某一评价维度的多模型评分", {
    x: 4.9, y: 2.25, w: 2.9, h: 0.2, fontSize: 13.5, bold: true, color: C.ink, margin: 0,
  });
  const rows = [
    ["Model A", "81", C.navy],
    ["Model B", "84", C.teal],
    ["Model C", "79", C.bronze],
  ];
  rows.forEach((row, i) => {
    const y = 2.8 + i * 0.78;
    slide.addShape(pptx.ShapeType.rect, {
      x: 4.9, y, w: 3.9, h: 0.52, fill: { color: i % 2 ? "F8F4EE" : "F2F7FA" }, line: { color: "FFFFFF", transparency: 100 },
    });
    slide.addText(row[0], {
      x: 5.15, y: y + 0.16, w: 1.2, h: 0.15, fontFace: "Calibri", fontSize: 12.5, bold: true, color: row[2], margin: 0,
    });
    slide.addText(row[1], {
      x: 7.35, y: y + 0.12, w: 0.7, h: 0.2, fontFace: "Calibri", fontSize: 17, bold: true, color: C.ink, align: "center", margin: 0,
    });
  });
  addStat(slide, 9.2, 2.72, 1.15, 0.95, "81.3", "Mean", C.navy);
  addStat(slide, 10.6, 2.72, 1.15, 0.95, "2.1", "Std", C.bronze);
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 9.15, y: 4.6, w: 2.62, h: 1.1, rectRadius: 0.06, fill: { color: "EEF6F3" }, line: { color: "BCD6D3", width: 1 },
  });
  slide.addText("结果展示口径：\n原始分数列表 / 均值 / 标准差 / 置信标签", {
    x: 9.4, y: 4.9, w: 2.12, h: 0.5, fontSize: 12, bold: true, color: C.teal, align: "center", margin: 0, breakLine: true, fit: "shrink",
  });
}

function addSlide11() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 11, "REVIEW");
  addTitle(slide, "专家复核：在分歧处引入高质量人工判断", "Expert Review as Human-in-the-Loop");
  addBullets(slide, [
    "低置信度维度或论文自动进入专家复核队列。",
    "编辑也可对高置信度结果追加复核，以满足制度要求。",
    "专家评分与 AI 评分并列存储，不互相覆盖，保留判断差异。",
  ], { x: 0.95, y: 1.85, w: 4.7, h: 2.7, fontSize: 15.2 });
  addCard(slide, 5.95, 1.95, 6.25, 4.75, { fill: C.white, line: C.line, shadow: true });
  slide.addText("AI 初评", {
    x: 6.32, y: 2.2, w: 1.0, h: 0.16, fontSize: 13.5, bold: true, color: C.navy, margin: 0,
  });
  slide.addText("专家复核", {
    x: 9.52, y: 2.2, w: 1.2, h: 0.16, fontSize: 13.5, bold: true, color: C.teal, margin: 0,
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 6.25, y: 2.62, w: 2.4, h: 3.35, fill: { color: "F2F7FA" }, line: { color: "BFD1DF", width: 1 },
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 9.45, y: 2.62, w: 2.4, h: 3.35, fill: { color: "F7FBFA" }, line: { color: "BCD6D3", width: 1 },
  });
  const dims = ["创新性", "洞察度", "建构力", "严密性"];
  dims.forEach((t, i) => {
    slide.addText(`${t}  ${[82, 79, 84, 80][i]}`, {
      x: 6.5, y: 2.95 + i * 0.62, w: 1.8, h: 0.16, fontSize: 11.5, color: C.ink, margin: 0,
    });
    slide.addText(`${t}  ${[80, 83, 85, 78][i]}`, {
      x: 9.7, y: 2.95 + i * 0.62, w: 1.8, h: 0.16, fontSize: 11.5, color: C.ink, margin: 0,
    });
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 8.77, y: 4.32, w: 0.48, h: 0, line: { color: C.bronze, width: 1.6, beginArrowType: "triangle", endArrowType: "triangle" },
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 7.45, y: 5.18, w: 3.2, h: 0.78, rectRadius: 0.06, fill: { color: "FBF6EF" }, line: { color: "DCCBAE", width: 1 },
  });
  slide.addText("parallel records / 不覆盖，只并列", {
    x: 7.7, y: 5.46, w: 2.7, h: 0.15, fontFace: "Calibri", fontSize: 12.2, bold: true, color: C.bronze, align: "center", margin: 0,
  });
  addFooterNote(slide, "系统不是“AI 替代人”，而是“AI 先行筛查，专家聚焦介入”。");
}

function addSlide12() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 12, "REPORTING");
  addTitle(slide, "报告输出：从黑箱分数到可解释评价", "Explainable and Standardized Reporting");
  addCard(slide, 0.95, 1.95, 4.9, 4.9, { fill: C.white, line: C.line, shadow: true });
  addCard(slide, 6.15, 1.95, 4.9, 4.9, { fill: C.white, line: C.line, shadow: true });
  addLabel(slide, "Public Report", 1.25, 2.18, 1.45, C.white, C.navy);
  addLabel(slide, "Internal Report", 6.45, 2.18, 1.55, C.white, C.teal);
  slide.addText("面向投稿人", {
    x: 1.28, y: 2.66, w: 1.0, h: 0.16, fontSize: 12.5, bold: true, color: C.ink, margin: 0,
  });
  slide.addText("面向编辑 / 专家 / 管理员", {
    x: 6.48, y: 2.66, w: 2.0, h: 0.16, fontSize: 12.5, bold: true, color: C.ink, margin: 0,
  });
  addMiniBulletList(slide, [
    "六维评分与加权总分",
    "六维雷达图与维度简评",
    "整体评价与专家意见摘要",
    "任务完成后统一公开",
  ], 1.25, 3.05, 3.9, 1.8);
  addMiniBulletList(slide, [
    "均值 ± 标准差与置信标签",
    "证据引用与 AI 分析说明",
    "多模型原始评分与一致性数据",
    "专家复核意见与报告版本",
  ], 6.45, 3.05, 3.9, 1.8);
  slide.addShape(pptx.ShapeType.rect, {
    x: 1.28, y: 5.15, w: 3.95, h: 1.18, fill: { color: "F2F7FA" }, line: { color: "BFD1DF", width: 1 },
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 6.48, y: 5.15, w: 3.95, h: 1.18, fill: { color: "F7FBFA" }, line: { color: "BCD6D3", width: 1 },
  });
  slide.addText("标准化结果报告", {
    x: 1.55, y: 5.4, w: 1.3, h: 0.18, fontSize: 13, bold: true, color: C.navy, margin: 0,
  });
  slide.addText("可追溯内部完整报告", {
    x: 6.75, y: 5.4, w: 1.8, h: 0.18, fontSize: 13, bold: true, color: C.teal, margin: 0,
  });
  addStat(slide, 11.35, 2.2, 1.2, 0.95, "vN", "快照版本", C.bronze);
  addStat(slide, 11.35, 3.45, 1.2, 0.95, "JSON", "系统集成", C.navy);
  addStat(slide, 11.35, 4.7, 1.2, 0.95, "PDF", "人工阅读", C.teal);
}

function addSlide13() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 13, "ARCHITECTURE");
  addTitle(slide, "系统架构：面向扩展的人文社科评价底座", "Modular Architecture for Scalable Scholarly Evaluation");
  const modules = [
    ["ingestion", 0.95, 2.1, C.navy],
    ["knowledge", 3.05, 2.1, C.teal],
    ["evaluation", 5.15, 2.1, C.bronze],
    ["reliability", 7.25, 2.1, C.red],
    ["review", 9.35, 2.1, "6A5B8C"],
    ["reporting", 11.0, 2.1, "546A7B"],
  ];
  modules.forEach(([name, x, y, color], i) => {
    addCard(slide, x, y, i === 5 ? 1.35 : 1.7, 1.2, { fill: C.white, line: C.line, shadow: true });
    slide.addShape(pptx.ShapeType.rect, {
      x, y, w: i === 5 ? 1.35 : 1.7, h: 0.2, fill: { color }, line: { color, transparency: 100 },
    });
    slide.addText(name, {
      x: x + 0.12, y: y + 0.38, w: (i === 5 ? 1.35 : 1.7) - 0.24, h: 0.18, fontFace: "Calibri", fontSize: 12.5, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink",
    });
  });
  addCard(slide, 2.2, 4.05, 4.4, 1.4, { fill: "F7FBFA", line: "BCD6D3" });
  addCard(slide, 6.95, 4.05, 4.4, 1.4, { fill: "F2F7FA", line: "BFD1DF" });
  slide.addText("Knowledge Frameworks", {
    x: 2.45, y: 4.34, w: 1.9, h: 0.18, fontFace: "Calibri", fontSize: 14, bold: true, color: C.teal, margin: 0,
  });
  slide.addText("YAML / JSON 外部配置加载\n维度、权重、阈值不硬编码", {
    x: 2.45, y: 4.68, w: 3.6, h: 0.4, fontSize: 12, color: C.ink, margin: 0, breakLine: true, fit: "shrink",
  });
  slide.addText("Audit & Storage", {
    x: 7.2, y: 4.34, w: 1.6, h: 0.18, fontFace: "Calibri", fontSize: 14, bold: true, color: C.navy, margin: 0,
  });
  slide.addText("AI 输入输出、预处理结果、报告版本与访问审计长期保留", {
    x: 7.2, y: 4.68, w: 3.75, h: 0.36, fontSize: 12, color: C.ink, margin: 0, fit: "shrink",
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 4.4, y: 3.34, w: 0, h: 0.68, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 8.95, y: 3.34, w: 0, h: 0.68, line: { color: "9EB2C4", width: 1.1, endArrowType: "triangle" },
  });
  addCard(slide, 3.45, 5.95, 5.9, 0.65, { fill: C.white, line: C.line });
  slide.addText("统一 Provider 抽象 + 模块化边界，让法学先行方案可扩展到更多人文社科学科。", {
    x: 3.72, y: 6.17, w: 5.35, h: 0.18, fontSize: 12.2, bold: true, color: C.bronze, align: "center", margin: 0, fit: "shrink",
  });
}

function addSlide14() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 14, "PROGRESS");
  addTitle(slide, "当前进展与近期里程碑", "Current Progress and Near-Term Milestones");
  addBullets(slide, [
    "当前已推进文档摄取、知识框架加载、AI provider 抽象、可靠性计算等核心底座。",
    "近期目标是打通“上传论文 → 自动评审 → 内部报告查看”的最小闭环。",
    "下一阶段将补齐专家复核、公开报告、审计留存、批量任务与恢复机制。",
  ], { x: 0.95, y: 1.9, w: 4.65, h: 2.7, fontSize: 15.1 });
  const milestones = [
    ["M1", "自动评审闭环", "已在推进", C.navy, 6.0],
    ["M2", "专家复核", "下一阶段", C.teal, 7.6],
    ["M3", "报告版本化 / 审计", "规划中", C.bronze, 9.2],
    ["M4", "批量任务 / 恢复", "规划中", C.red, 10.8],
  ];
  slide.addShape(pptx.ShapeType.line, {
    x: 6.45, y: 4.85, w: 5.0, h: 0, line: { color: "B8C7D3", width: 2 },
  });
  milestones.forEach(([m, title, state, color, x], i) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x, y: 4.55, w: 0.55, h: 0.55, fill: { color }, line: { color, transparency: 100 },
    });
    slide.addText(m, {
      x, y: 4.73, w: 0.55, h: 0.12, fontFace: "Calibri", fontSize: 10.5, bold: true, color: C.white, align: "center", margin: 0,
    });
    addCard(slide, x - 0.55, 5.35, 1.65, 1.15, { fill: C.white, line: C.line });
    slide.addText(title, {
      x: x - 0.45, y: 5.62, w: 1.45, h: 0.2, fontSize: 11.2, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink",
    });
    slide.addText(state, {
      x: x - 0.4, y: 5.98, w: 1.35, h: 0.14, fontSize: 9.5, color: color, align: "center", margin: 0,
    });
  });
  addStat(slide, 0.98, 5.25, 1.45, 0.92, "v0.4", "需求基线", C.bronze);
  addStat(slide, 2.68, 5.25, 1.45, 0.92, "MVP", "演示闭环", C.navy);
  addStat(slide, 4.38, 5.25, 1.45, 0.92, "v1", "逐步扩展", C.teal);
}

function addSlide15() {
  const slide = pptx.addSlide();
  addLightFrame(slide, 15, "CONCLUSION");
  addTitle(slide, "结语：AI 辅助学术评价的边界与前景", "Conclusion: Boundaries and Future of AI-Assisted Evaluation", {
    x: 0.95, y: 0.82, w: 8.6, titleSize: 24,
  });
  const cards = [
    ["标准显化", "评价不再只依赖隐性经验，而是把学科标准显化为可定义、可讨论、可演化的结构。"],
    ["结果可信", "均值、标准差、专家复核与版本审计共同构成了可解释、可追溯的可信链条。"],
    ["跨学科扩展", "从法学出发，未来可迁移到更广泛的人文社科评价场景。"],
  ];
  cards.forEach((card, i) => {
    addCard(slide, 1.05 + i * 4.05, 2.15, 3.45, 2.25, {
      fill: C.white,
      line: C.lineDark,
      shadow: true,
    });
    slide.addShape(pptx.ShapeType.rect, {
      x: 1.05 + i * 4.05,
      y: 2.15,
      w: 3.45,
      h: 0.18,
      fill: { color: i === 1 ? C.accentBlue : C.primary },
      line: { color: i === 1 ? C.accentBlue : C.primary, transparency: 100 },
    });
    slide.addText(card[0], {
      x: 1.35 + i * 4.05, y: 2.58, w: 2.85, h: 0.22, fontSize: 15.5, bold: true, color: i === 1 ? C.accentBlue : C.primary, align: "center", margin: 0,
    });
    slide.addText(card[1], {
      x: 1.35 + i * 4.05, y: 3.05, w: 2.85, h: 1.0, fontSize: 12.2, color: C.ink, margin: 0, align: "center", fit: "shrink",
    });
  });
  slide.addImage({
    path: A.gate,
    x: 3.15,
    y: 3.95,
    w: 7.1,
    h: 2.3,
  });
  slide.addText("自主知识体系 + AI + 专家复核\n构成一条兼顾学理基础与技术能力的折中路径", {
    x: 2.55,
    y: 5.45,
    w: 7.7,
    h: 0.72,
    fontSize: 19,
    bold: true,
    color: C.primary,
    align: "center",
    margin: 0,
    breakLine: true,
    fit: "shrink",
  });
  addFooterNote(slide, "Future target: explainable, auditable, and extensible infrastructure for scholarly evaluation.");
}

function addSlide16() {
  const slide = pptx.addSlide();
  slide.background = { path: A.bg };
  addBrandHeader(slide, true);
  slide.addImage({
    path: A.gateWide,
    x: 0.0,
    y: 3.55,
    w: 13.33,
    h: 3.75,
  });
  slide.addText("致谢", {
    x: 4.9,
    y: 1.95,
    w: 3.6,
    h: 0.48,
    fontSize: 30,
    bold: true,
    color: C.primary,
    align: "center",
    margin: 0,
  });
  slide.addText("Acknowledgements", {
    x: 4.75,
    y: 2.45,
    w: 3.9,
    h: 0.22,
    fontFace: "Calibri",
    fontSize: 14,
    italic: true,
    color: C.accentSlate,
    align: "center",
    margin: 0,
  });
  slide.addText("感谢各位专家、老师与同仁的聆听与指正", {
    x: 3.2,
    y: 3.0,
    w: 6.95,
    h: 0.38,
    fontSize: 20,
    bold: true,
    color: C.accentSlate,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  slide.addText("欢迎围绕自主知识体系、AI 辅助评价、法学与人文社科拓展合作继续交流", {
    x: 2.2,
    y: 3.45,
    w: 8.95,
    h: 0.26,
    fontSize: 13.5,
    color: C.accentSlate,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  slide.addText("Thank You / Q&A", {
    x: 5.05,
    y: 5.15,
    w: 3.2,
    h: 0.28,
    fontFace: "Calibri",
    fontSize: 18,
    bold: true,
    color: C.primary,
    align: "center",
    margin: 0,
  });
  addFooterMotto(slide);
}

[
  addSlide1,
  addSlide2,
  addSlide3,
  addSlide4,
  addSlide5,
  addSlide6,
  addSlide7,
  addSlide8,
  addSlide9,
  addSlide10,
  addSlide11,
  addSlide12,
  addSlide13,
  addSlide14,
  addSlide15,
  addSlide16,
].forEach((fn) => fn());

pptx.writeFile({ fileName: "docs/presentations/2026-03-19-ai-assisted-academic-evaluation-system.pptx" });
