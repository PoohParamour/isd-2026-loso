/** Benchmark the Lab 7 local VLM pipeline on the fixed dev split. */

import fs from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";

const ROOT = path.resolve(import.meta.dirname, "..");
const OLLAMA = process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
const OCR_MODEL = process.env.VLM_OCR_MODEL || "scb10x/typhoon-ocr1.5-3b";
const TEXT_MODEL = process.env.VLM_TEXT_MODEL || "qwen3:4b";
const NULL_STRING = { type: ["string", "null"] };
const NULL_INTEGER = { type: ["integer", "null"] };

const SCHEMA = {
  type: "object",
  properties: {
    header_detail: {
      type: "object",
      properties: {
        uni_name: NULL_STRING, uni_address: NULL_STRING, student_id: NULL_STRING,
        faculty_name: NULL_STRING, prename: NULL_STRING, name: NULL_STRING,
        date_of_birth: NULL_STRING, admis_date: NULL_STRING, grad_date: NULL_STRING,
        grad_reason: NULL_STRING, degree: NULL_STRING, major: NULL_STRING,
        program: NULL_STRING, honor: NULL_INTEGER,
      },
      required: ["student_id", "prename", "name", "faculty_name"],
    },
    transcript_detail: {
      type: "object",
      properties: {
        semesters: {
          type: "array",
          items: {
            type: "object",
            properties: {
              year: NULL_INTEGER, sem_num: NULL_INTEGER, GPA: NULL_STRING,
              GPS: NULL_STRING, pass_reason: NULL_STRING,
              subject: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    subject_id: NULL_STRING, subject_name: NULL_STRING,
                    type: NULL_STRING, credit: NULL_INTEGER, grade_earn: NULL_STRING,
                  },
                  required: ["subject_id", "subject_name", "credit", "grade_earn"],
                },
              },
            },
            required: ["year", "sem_num", "subject"],
          },
        },
        master_comprehensive: NULL_STRING, master_thesis: NULL_STRING,
        master_qualify: NULL_STRING, total_credits_earned: NULL_INTEGER,
        cumulative_gpa: NULL_STRING,
      },
      required: ["semesters"],
    },
    footer_detail: {
      type: "object",
      properties: {
        updated_at: NULL_STRING,
        by: {
          type: "object",
          properties: { by_signature: NULL_STRING, by_position: NULL_STRING, by_reg: NULL_STRING },
        },
      },
    },
  },
  required: ["header_detail", "transcript_detail"],
};

const OCR_PROMPT = "Below is an image of a document page. Extract all text content and structure into markdown format. Preserve tables using markdown table syntax.";
const SYSTEM_PROMPT = "You are a precise document transcription system for Thai university transcripts. Transcribe exactly what is printed. Never infer, correct, complete, or beautify. When something is unreadable output null. You are penalised heavily for guessing.";
const JSON_PROMPT = (text) => `Convert the following Thai university transcript OCR into the required JSON schema.
Rules: copy only visible values; never guess; use null when unreadable; read every table row top-to-bottom and the left column before the right; do not calculate GPA or GPS. GPS is the semester GPA and GPA is cumulative. Preserve every course including transfer, W, and repeated courses. Dates must be YYYY-MM-DD, Thai digits must become Arabic digits, and credit must be an integer.

DOCUMENT OCR:
${text}

Return JSON only.`;

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

async function chat(model, messages, format) {
  const response = await fetch(`${OLLAMA}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model, messages, stream: false,
      think: false,
      options: { temperature: 0, num_ctx: 16384, num_predict: 4096 },
      ...(format ? { format } : {}),
    }),
    signal: AbortSignal.timeout(Number(process.env.VLM_TIMEOUT_MS || 180000)),
  });
  if (!response.ok) throw new Error(`${model}: HTTP ${response.status} ${await response.text()}`);
  const body = await response.json();
  if (!body.message?.content?.trim()) throw new Error(`${model}: empty response`);
  return body.message.content;
}

function normal(value) {
  if (value === null || value === undefined) return "";
  return String(value).normalize("NFKC").toLowerCase().replace(/\s+/g, "").trim();
}

function score(prediction, truth) {
  let correct = 0;
  let total = 0;
  const compare = (actual, expected) => {
    if (expected === null || expected === "") return;
    total += 1;
    if (normal(actual) === normal(expected)) correct += 1;
  };
  const ph = prediction.header_detail || {};
  const gh = truth.header_detail || {};
  for (const key of Object.keys(gh)) {
    if (key !== "by") compare(ph[key], gh[key]);
  }
  const pt = prediction.transcript_detail || {};
  const gt = truth.transcript_detail || {};
  for (const key of ["master_comprehensive", "master_thesis", "master_qualify", "total_credits_earned", "cumulative_gpa"]) compare(pt[key], gt[key]);
  const predictedSemesters = pt.semesters || [];
  for (const semester of gt.semesters || []) {
    const match = predictedSemesters.find((item) => normal(item.year) === normal(semester.year) && normal(item.sem_num) === normal(semester.sem_num)) || {};
    for (const key of ["year", "sem_num", "GPA", "GPS", "pass_reason"]) compare(match[key], semester[key]);
    const predictedSubjects = match.subject || [];
    const used = new Set();
    for (const subject of semester.subject || []) {
      const index = predictedSubjects.findIndex((item, i) => !used.has(i) && normal(item.subject_id) === normal(subject.subject_id));
      const found = index >= 0 ? predictedSubjects[index] : {};
      if (index >= 0) used.add(index);
      for (const key of ["subject_id", "subject_name", "type", "credit", "grade_earn"]) compare(found[key], subject[key]);
    }
  }
  const pf = prediction.footer_detail || {};
  const gf = truth.footer_detail || {};
  compare(pf.updated_at, gf.updated_at);
  for (const key of ["by_signature", "by_position", "by_reg"]) compare(pf.by?.[key], gf.by?.[key]);
  return { correct, total, accuracy: total ? correct / total : 0 };
}

async function main() {
  const perGroup = Number(arg("--per-group", "1"));
  const output = path.resolve(ROOT, arg("--out", "model/reports/vlm-dev.json"));
  const manifest = JSON.parse(await fs.readFile(path.join(ROOT, "model/data/manifest.json"), "utf8"));
  let previousDetails = new Map();
  try {
    const previous = JSON.parse(await fs.readFile(output, "utf8"));
    previousDetails = new Map((previous.details || []).map((row) => [row.id, row]));
  } catch {}
  const selected = [];
  for (const group of ["bachelor", "graduate"]) {
    for (const language of ["th", "en"]) {
      selected.push(...manifest.documents.filter((doc) => doc.split === "dev" && doc.group === group && doc.language === language).sort((a, b) => a.id.localeCompare(b.id)).slice(0, perGroup));
    }
  }
  const details = [];
  const intermediate = path.join(path.dirname(output), "vlm-intermediate");
  await fs.mkdir(intermediate, { recursive: true });
  const saveReport = async () => {
    const successful = details.filter((row) => !row.error);
    const timed = successful.filter((row) => typeof row.seconds === "number");
    const correct = successful.reduce((sum, row) => sum + row.correct, 0);
    const total = successful.reduce((sum, row) => sum + row.total, 0);
    const report = {
      split: "dev", input: "Lab5 original PNG, 150 DPI",
      pipeline: `${OCR_MODEL} -> ${TEXT_MODEL}`, api_cost_usd: 0,
      documents_attempted: details.length, documents_succeeded: successful.length,
      correct, total, exact_field_accuracy: total ? correct / total : 0,
      mean_seconds: timed.length ? timed.reduce((sum, row) => sum + row.seconds, 0) / timed.length : null,
      details,
    };
    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    return report;
  };
  for (const doc of selected) {
    const started = performance.now();
    const truth = JSON.parse(await fs.readFile(path.join(ROOT, doc.gt), "utf8"));
    try {
      const mdPath = path.join(intermediate, `${doc.id}.md`);
      const jsonPath = path.join(intermediate, `${doc.id}.json`);
      let markdown;
      let prediction;
      let cached = false;
      try {
        markdown = await fs.readFile(mdPath, "utf8");
        prediction = JSON.parse(await fs.readFile(jsonPath, "utf8"));
        cached = true;
      } catch {
        const imageFolder = doc.group === "graduate" ? "G" : "th";
        const imagePath = path.join(ROOT, "all/Lab5_transcript_dataset/images/original", imageFolder, `${doc.id}.png`);
        const image = (await fs.readFile(imagePath)).toString("base64");
        markdown = await chat(OCR_MODEL, [{ role: "user", content: OCR_PROMPT, images: [image] }]);
        await fs.writeFile(mdPath, markdown, "utf8");
        const raw = await chat(TEXT_MODEL, [{ role: "system", content: SYSTEM_PROMPT }, { role: "user", content: JSON_PROMPT(markdown) }], SCHEMA);
        prediction = JSON.parse(raw);
        await fs.writeFile(jsonPath, `${JSON.stringify(prediction, null, 2)}\n`, "utf8");
      }
      const previousSeconds = previousDetails.get(doc.id)?.seconds;
      const result = { id: doc.id, group: doc.group, language: doc.language, seconds: cached ? (previousSeconds ?? null) : Math.round((performance.now() - started) / 100) / 10, cached, ...score(prediction, truth) };
      details.push(result);
      console.log(`${result.id} ${result.group}_${result.language} ${result.correct}/${result.total} ${(result.accuracy * 100).toFixed(2)}% ${result.seconds}s`);
    } catch (error) {
      const result = { id: doc.id, group: doc.group, language: doc.language, seconds: Math.round((performance.now() - started) / 100) / 10, error: String(error?.message || error) };
      details.push(result);
      console.error(`${result.id} ${result.group}_${result.language} FAILED ${result.seconds}s ${result.error}`);
    }
    await saveReport();
  }
  const report = await saveReport();
  console.log(JSON.stringify({ ...report, details: undefined }, null, 2));
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
