"use client";

import { useEffect, useId, useRef, useState } from "react";

type Course = { subject_id?: string; subject_name?: string; credit?: number; grade_earn?: string };
type Semester = { year?: number; sem_num?: number; GPA?: string; subject?: Course[] };
type RecordData = {
  format_id?: string;
  header_detail?: { student_id?: string; prename?: string; name?: string; program?: string };
  transcript_detail?: { semesters?: Semester[]; total_credits_earned?: number; cumulative_gpa?: string };
};
type ValidationIssue = { path: string; code: string; message: string; severity: "error" | "warning" };
type Validation = { needs_review: boolean; errors: number; warnings: number; course_count: number; issues: ValidationIssue[] };
type Extraction = { filename: string; engine: string; processing_seconds: number; record: RecordData; validation?: Validation; error?: string };
type Grade = { student_id: string; academic_year: string; semester_number: string; subject_id: string; subject_name: string; grade: string };
type Notice = { text: string; tone: "info" | "success" | "error" };

const PAGE_RATIO = 210 / 297; // A4 portrait, width / height
const MAX_UPLOAD = 20 * 1024 * 1024;
const ALLOWED = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif"];
const ACCEPT = ALLOWED.join(",") + ",image/heic,image/heif";

const formatOptions: [string, string][] = [
  ["auto", "ตรวจรูปแบบอัตโนมัติ"],
  ["bachelor_th", "ปริญญาตรี · ไทย"],
  ["bachelor_en", "ปริญญาตรี · อังกฤษ"],
  ["graduate_th", "บัณฑิตศึกษา · ไทย"],
  ["graduate_en", "บัณฑิตศึกษา · อังกฤษ"],
];
const formatLabel = (id?: string) => formatOptions.find(([value]) => value === id)?.[1] || id || "—";

const noticeStyle: Record<Notice["tone"], string> = {
  info: "border-blue-200 bg-blue-50 text-blue-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  error: "border-red-200 bg-red-50 text-red-800",
};

async function api(path: string, init?: RequestInit) {
  const response = await fetch("/api/proxy/" + path, { cache: "no-store", ...init });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "HTTP " + response.status);
  return data;
}

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));

function fileExtension(name: string) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function checkFile(file: File) {
  if (!ALLOWED.includes(fileExtension(file.name))) return "ไม่รองรับไฟล์ชนิดนี้ (รองรับ PDF, PNG, JPG, TIFF, HEIC)";
  if (file.size > MAX_UPLOAD) return "ไฟล์ใหญ่เกิน 20 MB";
  return "";
}

// Turns "transcript_detail.semesters[0].subject[2].grade_earn" into a readable location.
function describePath(path: string, semesters: Semester[]) {
  if (path.startsWith("header_detail")) return "ข้อมูลนักศึกษา";
  if (path.startsWith("input")) return "ไฟล์ต้นฉบับ";
  const match = path.match(/semesters\[(\d+)\](?:\.subject\[(\d+)\])?/);
  if (!match) return "ภาพรวม transcript";
  const semester = semesters[Number(match[1])];
  const term = "ภาค " + (semester?.sem_num ?? "?") + "/" + (semester?.year ?? "?");
  if (match[2] === undefined) return term;
  const course = semester?.subject?.[Number(match[2])];
  return term + " · " + (course?.subject_id || "แถวที่ " + (Number(match[2]) + 1));
}

type Suggestion = { value: string; label: string };

function SuggestInput({ label, kind, digits, placeholder, value, onChange }: {
  label: string; kind: "student" | "subject"; digits: number; placeholder: string;
  value: string; onChange: (value: string) => void;
}) {
  const [items, setItems] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const wrapper = useRef<HTMLLabelElement>(null);
  const listId = useId();
  // Hide results that belong to an older (or cleared) input without resetting state in an effect.
  const shown = open && value ? items.filter(item => item.value.startsWith(value)) : [];

  useEffect(() => {
    if (!open || !value) return;
    let stale = false;
    const timer = setTimeout(async () => {
      try {
        const data = await api("suggest?" + new URLSearchParams({ kind, q: value }).toString());
        if (!stale) { setItems(data.results || []); setActive(-1); }
      } catch { if (!stale) setItems([]); }
    }, 150);
    return () => { stale = true; clearTimeout(timer); };
  }, [value, open, kind]);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function pick(item: Suggestion) { onChange(item.value); setOpen(false); }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown" && shown.length) { event.preventDefault(); setOpen(true); setActive(index => (index + 1) % shown.length); }
    else if (event.key === "ArrowUp" && shown.length) { event.preventDefault(); setActive(index => (index <= 0 ? shown.length - 1 : index - 1)); }
    else if (event.key === "Enter" && active >= 0 && shown[active]) { event.preventDefault(); pick(shown[active]); }
    else if (event.key === "Escape") setOpen(false);
  }

  const complete = value.length === digits;
  return (
    <label ref={wrapper} className="relative block text-[12px] text-[#716F6A]">
      {label}
      <input
        value={value}
        onChange={e => { onChange(e.target.value.replace(/\D/g, "").slice(0, digits)); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        inputMode="numeric" autoComplete="off" maxLength={digits} placeholder={placeholder}
        role="combobox" aria-expanded={shown.length > 0} aria-controls={listId} aria-autocomplete="list"
        className="mt-2 block w-full h-[44px] px-4 border border-[#E7E4DE] rounded-[14px] text-[14px] text-[#292825] focus:outline-none focus:border-[#F47721]"
      />
      <span className={`mt-1 block text-[11px] ${complete ? "text-[#3E8D67]" : "text-[#716F6A]"}`}>
        {value ? value.length + "/" + digits + " หลัก" : "ตัวเลข " + digits + " หลัก"}
      </span>
      {shown.length > 0 && (
        <ul id={listId} role="listbox" className="absolute z-20 left-0 right-0 top-[72px] max-h-[260px] overflow-y-auto bg-white border border-[#E7E4DE] rounded-[14px] shadow-lg py-1">
          {shown.map((item, i) => (
            <li key={item.value} role="option" aria-selected={i === active}
              onMouseDown={e => { e.preventDefault(); pick(item); }}
              onMouseEnter={() => setActive(i)}
              className={`px-4 py-2 cursor-pointer flex items-baseline gap-3 ${i === active ? "bg-orange-50" : ""}`}>
              <span className="font-mono text-[13px] text-[#292825]">
                <b className="text-[#F47721]">{item.value.slice(0, value.length)}</b>{item.value.slice(value.length)}
              </span>
              <span className="text-[12px] text-[#716F6A] truncate">{item.label}</span>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}

export default function Home() {
  const [currentTab, setCurrentTab] = useState<"upload" | "search">("upload");
  const [isDragging, setIsDragging] = useState(false);
  const [format, setFormat] = useState("auto");
  const [forceOcr, setForceOcr] = useState(false);
  const [results, setResults] = useState<Extraction[]>([]);
  const [selected, setSelected] = useState(0);
  const [saved, setSaved] = useState<Record<number, string>>({});
  const [extracting, setExtracting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [progress, setProgress] = useState("");

  const [studentId, setStudentId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [searched, setSearched] = useState(false);

  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [editor, setEditor] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const captureInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);

  useEffect(() => {
    if (cameraStream && videoRef.current) videoRef.current.srcObject = cameraStream;
    return () => cameraStream?.getTracks().forEach(track => track.stop());
  }, [cameraStream]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setGuideOpen(false);
      setCameraStream(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const current = results[selected];
  let record: RecordData | undefined;
  let jsonError = "";
  if (current && !current.error) {
    try { record = JSON.parse(editor) as RecordData; }
    catch { jsonError = "JSON ไม่ถูกต้อง กรุณาตรวจวงเล็บและเครื่องหมาย"; }
  }
  const semesters = record?.transcript_detail?.semesters || [];
  const courses = semesters.reduce((count, semester) => count + (semester.subject?.length || 0), 0);
  const issues = current?.validation?.issues || [];
  const edited = !!current && !current.error && !jsonError && editor !== JSON.stringify(current.record, null, 2);

  function courseIssues(semIndex: number, rowIndex: number) {
    const prefix = "transcript_detail.semesters[" + semIndex + "].subject[" + rowIndex + "]";
    return issues.filter(issue => issue.path.startsWith(prefix));
  }
  const flaggedCourses = semesters.reduce((count, semester, s) =>
    count + (semester.subject || []).filter((_, r) => courseIssues(s, r).length > 0).length, 0);
  const passRate = courses ? Math.round(((courses - flaggedCourses) / courses) * 100) : 0;

  function select(index: number) {
    setCurrentTab("upload");
    setSelected(index);
    setEditor(JSON.stringify(results[index].record, null, 2));
    setNotice(null);
  }

  function resetUpload() {
    setResults([]); setSelected(0); setSaved({}); setEditor(""); setNotice(null); setShowJsonEditor(false);
  }

  async function extractAll(filesToExtract: File[]) {
    if (!filesToExtract.length) return;
    setCurrentTab("upload");
    setExtracting(true); setNotice(null); setResults([]); setSelected(0); setSaved({}); setShowJsonEditor(false);
    const next: Extraction[] = [];
    try {
      for (let i = 0; i < filesToExtract.length; i++) {
        const file = filesToExtract[i];
        setProgress("กำลังอ่าน " + (i + 1) + "/" + filesToExtract.length + ": " + file.name);
        const invalid = checkFile(file);
        if (invalid) {
          next.push({ filename: file.name, engine: "", processing_seconds: 0, record: {}, error: invalid });
          setResults([...next]);
          continue;
        }
        const form = new FormData();
        form.append("file", file);
        if (format !== "auto") form.append("format_id", format);
        if (forceOcr) form.append("force_ocr", "true");
        try {
          next.push(await api("transcripts/extract", { method: "POST", body: form }) as Extraction);
        } catch (error) {
          next.push({ filename: file.name, engine: "", processing_seconds: 0, record: {}, error: errorText(error) });
        }
        setResults([...next]);
      }
      // Open the first readable document so a failed first file does not hide good ones.
      const first = Math.max(0, next.findIndex(item => !item.error));
      setSelected(first);
      setEditor(next[first].error ? "" : JSON.stringify(next[first].record, null, 2));
      const passed = next.filter(item => !item.error);
      const seconds = passed.reduce((sum, item) => sum + item.processing_seconds, 0);
      setNotice({
        text: "อ่านสำเร็จ " + passed.length + "/" + next.length + " ฉบับ · เวลา OCR รวม " + seconds.toFixed(2) + " วินาที",
        tone: passed.length === next.length ? "success" : passed.length ? "info" : "error",
      });
    } finally { setExtracting(false); setProgress(""); }
  }

  async function save() {
    if (!current || !record || jsonError) return;
    setBusy(true); setNotice(null);
    try {
      const result = await api("documents", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: current.filename, record, engine: current.engine, processing_seconds: current.processing_seconds }),
      });
      setSaved(previous => ({ ...previous, [selected]: result.document_id }));
      setNotice({ text: "บันทึกสำเร็จ · รหัสเอกสาร " + result.document_id, tone: "success" });
    } catch (error) { setNotice({ text: "บันทึกไม่สำเร็จ: " + errorText(error), tone: "error" }); }
    finally { setBusy(false); }
  }

  function updateEditor(value: string) {
    setEditor(value);
    // Edits after saving mean the stored copy is outdated.
    setSaved(previous => { const next = { ...previous }; delete next[selected]; return next; });
  }

  function formatJson() {
    if (record) setEditor(JSON.stringify(record, null, 2));
  }

  async function search(event?: React.FormEvent) {
    event?.preventDefault();
    if (!studentId.trim() && !subjectId.trim()) { setNotice({ text: "กรอกรหัสนักศึกษาหรือรหัสวิชาอย่างน้อยหนึ่งช่อง", tone: "error" }); return; }
    setBusy(true); setNotice(null);
    try {
      const params = new URLSearchParams();
      if (studentId.trim()) params.set("student_id", studentId.trim());
      if (subjectId.trim()) params.set("subject_id", subjectId.trim());
      const result = await api("grades?" + params.toString());
      setGrades(result.results || []);
      setSearched(true);
    } catch (error) { setNotice({ text: "ค้นหาไม่สำเร็จ: " + errorText(error), tone: "error" }); }
    finally { setBusy(false); }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) extractAll(Array.from(e.target.files));
    // Allow picking the same file again
    e.target.value = "";
  };

  async function openCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { captureInputRef.current?.click(); return; }
    try {
      setCameraStream(await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1080 }, height: { ideal: 1920 }, aspectRatio: { ideal: PAGE_RATIO } } }));
    } catch {
      setNotice({ text: "เปิดกล้องในเบราว์เซอร์ไม่ได้ (ต้องอนุญาตกล้องและเปิดผ่าน HTTPS หรือ localhost) จึงเปิดตัวเลือกถ่ายภาพของอุปกรณ์แทน", tone: "info" });
      captureInputRef.current?.click();
    }
  }

  function capturePhoto() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    // Crop the centre of the frame to the portrait page guide shown in the preview.
    const { videoWidth: vw, videoHeight: vh } = video;
    const cw = vw / vh > PAGE_RATIO ? vh * PAGE_RATIO : vw;
    const ch = vw / vh > PAGE_RATIO ? vh : vw / PAGE_RATIO;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(cw);
    canvas.height = Math.round(ch);
    canvas.getContext("2d")?.drawImage(video, (vw - cw) / 2, (vh - ch) / 2, cw, ch, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      if (!blob) return;
      setCameraStream(null);
      extractAll([new File([blob], "camera-" + Date.now() + ".jpg", { type: "image/jpeg" })]);
    }, "image/jpeg", 0.95);
  }

  const navButton = (active: boolean) =>
    `flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-colors ${active ? "bg-[#F47721] text-white" : "text-[#262626] hover:bg-slate-50"}`;

  return (
    <div className="min-h-screen bg-[#F8F7F5] text-[#292825]">
      <header className="h-[72px] bg-white flex items-center px-4 lg:px-12 border-b border-[#E7E4DE]">
        <div className="flex items-center gap-4">
          <div className="w-12 h-7 bg-[#ED0A13] rounded-[2px] flex items-center justify-center">
            <span className="font-['Inter'] font-black text-[12px] text-white tracking-widest">LOSO</span>
          </div>
          <h1 className="font-semibold text-[18px]">Transcript OCR Studio</h1>
        </div>
      </header>

      <div className="flex flex-col lg:flex-row px-4 lg:px-6 py-6 gap-6 max-w-[1440px] mx-auto lg:h-[calc(100vh-72px)] lg:overflow-hidden">
        <aside className="w-full lg:w-[224px] flex-shrink-0 bg-white rounded-[20px] border border-[#E7E4DE] p-4 flex flex-col lg:h-full lg:overflow-y-auto">
          <div className="text-[11px] text-[#716F6A] mb-2 px-2 tracking-wider font-semibold">WORKSPACE</div>
          <nav className="flex lg:flex-col gap-1 mb-6">
            <button onClick={() => { setCurrentTab("upload"); setNotice(null); }} className={navButton(currentTab === "upload") + " flex-1 lg:flex-none"}>
              <span className="font-semibold text-lg leading-none">↑</span>
              <span className="font-semibold text-[14px]">นำเข้า Transcript</span>
            </button>
            <button onClick={() => { setCurrentTab("search"); setNotice(null); }} className={navButton(currentTab === "search") + " flex-1 lg:flex-none"}>
              <span className="font-semibold text-lg leading-none">⌕</span>
              <span className="font-semibold text-[14px]">ค้นหาผลการเรียน</span>
            </button>
          </nav>

          <div className="h-[1px] bg-[#E7E4DE] mx-2 mb-6"></div>

          <div className="text-[11px] text-[#716F6A] mb-3 px-2 tracking-wider font-semibold">เอกสารในรอบนี้</div>
          {results.map((res, i) => (
            <button key={i} onClick={() => select(i)} className="px-2 mb-4 text-left group">
              <div className={`text-[13px] truncate ${selected === i && currentTab === "upload" ? "text-[#F47721] font-semibold" : "group-hover:text-[#F47721]"}`}>{res.filename}</div>
              <div className={`text-[11px] mt-1 ${res.error ? "text-red-600" : saved[i] ? "text-[#3E8D67]" : res.validation?.needs_review ? "text-[#A96519]" : "text-[#716F6A]"}`}>
                {res.error ? "อ่านไม่สำเร็จ" : saved[i] ? "บันทึกแล้ว" : res.validation?.needs_review ? "ควรตรวจสอบ" : "อ่านสำเร็จ"}
              </div>
            </button>
          ))}
          {results.length === 0 && <div className="px-2 text-[12px] text-[#716F6A]">{extracting ? "กำลังอ่าน..." : "ยังไม่มีเอกสาร"}</div>}

          <div className="mt-auto pt-6">
            <div className="border border-[#E7E4DE] rounded-2xl p-4">
              <div className="text-[12px] font-semibold">ต้องการความช่วยเหลือ?</div>
              <div className="text-[11px] text-[#716F6A] mt-2 leading-relaxed">คู่มือถ่ายเอกสารให้ OCR อ่านแม่นยำ</div>
              <button onClick={() => setGuideOpen(true)} className="text-[11px] text-[#F47721] mt-3 flex items-center gap-1 font-semibold hover:underline">
                เปิดคู่มือ <span className="text-[14px]">→</span>
              </button>
            </div>
          </div>
        </aside>

        <main className="flex-1 min-w-0 lg:overflow-y-auto lg:pr-2 pb-10">
          {notice && (
            <div role="status" className={`mb-6 rounded-xl border px-4 py-3 text-sm flex justify-between gap-4 ${noticeStyle[notice.tone]}`}>
              <span>{notice.text}</span>
              <button onClick={() => setNotice(null)} aria-label="ปิดข้อความ" className="opacity-60 hover:opacity-100">✕</button>
            </div>
          )}

          {extracting && (
            <div className="flex flex-col items-center justify-center pt-20">
              <div className="w-[72px] h-[72px] border-4 border-[#F47721] border-t-transparent rounded-full animate-spin mb-6"></div>
              <div className="text-[18px] font-semibold mb-2">กำลังประมวลผล</div>
              <div className="text-[14px] text-[#716F6A] text-center">{progress || "โปรดรอสักครู่..."}</div>
            </div>
          )}

          {currentTab === "upload" && results.length === 0 && !extracting && (
            <div className="max-w-[1040px]">
              <div className="text-[28px] font-semibold mb-2">นำเข้า Transcript</div>
              <div className="text-[14px] text-[#716F6A] mb-8 font-semibold">เลือกไฟล์จากอุปกรณ์ หรือถ่ายภาพเอกสารเพื่ออ่านเข้าสู่ระบบ</div>

              <div className="flex gap-6 items-start flex-col xl:flex-row">
                <div className="flex-1 w-full">
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => fileInputRef.current?.click()}
                    onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInputRef.current?.click(); } }}
                    onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={e => { e.preventDefault(); setIsDragging(false); }}
                    onDrop={e => {
                      e.preventDefault();
                      setIsDragging(false);
                      if (e.dataTransfer.files.length > 0) extractAll(Array.from(e.dataTransfer.files));
                    }}
                    className={`w-full min-h-[360px] px-4 border rounded-[24px] flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${isDragging ? "border-[#F47721] border-dashed border-2 bg-orange-50" : "bg-white border-[#E7E4DE] hover:bg-slate-50"}`}
                  >
                    <input ref={fileInputRef} type="file" multiple accept={ACCEPT} className="hidden" onChange={handleFileChange} />
                    <input ref={captureInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileChange} />
                    <div className="w-[72px] h-[72px] bg-white border border-[#E7E4DE] rounded-[20px] shadow-sm flex items-center justify-center mb-6">
                      <span className="text-[26px] font-semibold">↑</span>
                    </div>
                    <div className="text-[18px] font-semibold mb-2">{isDragging ? "ปล่อยไฟล์เพื่อเริ่มอ่าน" : "วางไฟล์ Transcript ที่นี่"}</div>
                    <div className="text-[13px] text-[#716F6A] mb-6">รองรับ PDF, JPG, PNG, TIFF และ HEIC · สูงสุด 20 MB ต่อไฟล์ · เลือกได้หลายไฟล์</div>
                    <div className="flex flex-col sm:flex-row gap-3 w-full max-w-[404px] justify-center">
                      <span className="sm:w-[196px] bg-[#F47721] text-white h-[44px] rounded-[14px] flex items-center justify-center text-[13px] font-medium hover:bg-orange-600">
                        เลือกไฟล์จากอุปกรณ์
                      </span>
                      <button type="button" onClick={e => { e.stopPropagation(); openCamera(); }} className="sm:w-[196px] bg-white border border-[#E7E4DE] h-[44px] rounded-[14px] flex items-center justify-center text-[13px] hover:bg-slate-50">
                        เปิดกล้องเพื่อถ่ายรูป
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 bg-white border border-[#E7E4DE] rounded-[18px] p-5 flex flex-col sm:flex-row sm:items-end gap-4">
                    <label className="flex-1 text-[12px] text-[#716F6A]">
                      รูปแบบเอกสาร
                      <select value={format} onChange={e => setFormat(e.target.value)} className="mt-2 block w-full h-[40px] px-3 bg-white border border-[#E7E4DE] rounded-[12px] text-[13px] text-[#292825] focus:outline-none focus:border-[#F47721]">
                        {formatOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label className="flex items-center gap-2 h-[40px] text-[13px] cursor-pointer" title="ใช้เมื่อ PDF เป็นภาพสแกน หรืออ่านข้อความจาก PDF แล้วผิดเพี้ยน">
                      <input type="checkbox" checked={forceOcr} onChange={e => setForceOcr(e.target.checked)} className="accent-[#F47721] w-4 h-4" />
                      บังคับอ่านด้วย OCR (สำหรับ PDF สแกน)
                    </label>
                  </div>
                </div>

                <div className="w-full xl:w-[304px] flex-shrink-0 bg-white border border-[#E7E4DE] rounded-[18px] p-6 shadow-sm">
                  <div className="font-semibold text-[14px] mb-1">เพื่อให้ OCR อ่านได้แม่นยำ</div>
                  <div className="text-[11px] text-[#716F6A] mb-4">แนะนำก่อนเลือกไฟล์</div>
                  <ul className="text-[12px] space-y-3 mb-6">
                    <li>- ใช้ PDF ต้นฉบับเป็นตัวเลือกแรก</li>
                    <li>- ภาพต้องคม ชัด และอ่านตัวอักษรได้</li>
                    <li>- ไม่เอียง ไม่กลับหัว และไม่ครอปข้อมูล</li>
                    <li>- หลีกเลี่ยงเงาและแสงสะท้อน</li>
                  </ul>
                  <button onClick={() => setGuideOpen(true)} className="text-[11px] font-semibold text-[#F47721] flex items-center gap-1 hover:underline">
                    ดู checklist ฉบับเต็ม <span className="text-[14px]">→</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {currentTab === "upload" && current?.error && !extracting && (
            <div className="max-w-[1040px] rounded-[22px] border border-red-200 bg-red-50 p-6 text-red-800">
              <div className="font-semibold mb-1">อ่านไฟล์ {current.filename} ไม่สำเร็จ</div>
              <div className="text-[13px]">{current.error}</div>
              <div className="flex gap-4 mt-4 text-[13px] font-semibold text-[#F47721]">
                <button onClick={resetUpload} className="hover:underline">← อัปโหลดไฟล์ใหม่</button>
                <button onClick={() => setGuideOpen(true)} className="hover:underline">ดูคำแนะนำการเตรียมไฟล์</button>
              </div>
            </div>
          )}

          {currentTab === "upload" && current && !current.error && !extracting && (
            <div className="flex gap-6 items-start flex-col xl:flex-row">
              <div className="flex-1 w-full min-w-0">
                <div className="text-[11px] text-[#716F6A] uppercase tracking-wider mb-2 truncate">TRANSCRIPT / {current.filename}</div>
                <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-4">
                  <div>
                    <div className="text-[30px] font-semibold leading-tight mb-2">ตรวจข้อมูลก่อนบันทึก</div>
                    <div className="text-[14px] text-[#716F6A] font-semibold">ตรวจและแก้ไขผล OCR ก่อนบันทึกเข้าสู่ระบบ</div>
                  </div>
                  <div className="flex gap-3 flex-shrink-0">
                    <button onClick={resetUpload} className="h-[46px] px-5 border border-[#E7E4DE] bg-white rounded-[14px] text-[13px] hover:bg-slate-50">อัปโหลดไฟล์ใหม่</button>
                    <button onClick={save} disabled={busy || !!jsonError || !!saved[selected]} className="bg-[#292825] text-white h-[46px] px-6 rounded-[14px] text-[14px] font-medium hover:bg-black disabled:opacity-50">
                      {busy ? "กำลังบันทึก..." : saved[selected] ? "บันทึกแล้ว ✓" : "บันทึกผลที่ตรวจแล้ว"}
                    </button>
                  </div>
                </div>

                <div className="bg-white border border-[#E7E4DE] rounded-[22px] p-6 mb-6 shadow-sm">
                  <div className="flex justify-between items-start gap-3 mb-6">
                    <div className="text-[15px] font-semibold">ข้อมูลนักศึกษา</div>
                    {current.validation && (
                      <div className="border border-[#E7E4DE] h-[30px] px-3 rounded-[15px] flex items-center gap-2 flex-shrink-0">
                        <div className={`w-1.5 h-1.5 rounded-full ${current.validation.needs_review ? "bg-[#F47721]" : "bg-[#3E8D67]"}`}></div>
                        <div className="text-[11px]">{current.validation.needs_review ? "ควรตรวจสอบ" : "ผ่านการตรวจอัตโนมัติ"}</div>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-x-8 gap-y-5">
                    {[
                      ["รหัสนักศึกษา", record?.header_detail?.student_id],
                      ["ชื่อ - นามสกุล", [record?.header_detail?.prename, record?.header_detail?.name].filter(Boolean).join(" ")],
                      ["หลักสูตร", record?.header_detail?.program],
                      ["เกรดเฉลี่ยสะสม", record?.transcript_detail?.cumulative_gpa],
                    ].map(([label, value]) => (
                      <div key={label} className="min-w-0">
                        <div className="text-[11px] text-[#716F6A] mb-1">{label}</div>
                        <div className="text-[16px] font-semibold [overflow-wrap:anywhere]">{value || "—"}</div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6 pt-4 border-t border-[#E7E4DE] text-[12px] text-[#716F6A]">
                    {formatLabel(record?.format_id)} · {semesters.length} ภาคการศึกษา · {courses} รายวิชา · {record?.transcript_detail?.total_credits_earned ?? "—"} หน่วยกิต
                  </div>
                </div>

                <div className="bg-white border border-[#E7E4DE] rounded-[22px] shadow-sm overflow-hidden">
                  <div className="p-6 flex justify-between items-center border-b border-[#E7E4DE]">
                    <div className="text-[16px] font-semibold">รายวิชาที่อ่านจากเอกสาร</div>
                    <div className="text-[12px] text-[#716F6A]">{courses} รายวิชา</div>
                  </div>
                  {jsonError ? (
                    <div className="p-6 text-[13px] text-red-600">{jsonError} · แก้ไขใน JSON editor เพื่อแสดงตาราง</div>
                  ) : courses === 0 ? (
                    <div className="p-6 text-[13px] text-[#716F6A]">ไม่พบรายวิชาในเอกสารนี้ ลองเลือกรูปแบบเอกสารเอง หรือเปิด “บังคับอ่านด้วย OCR” แล้วอ่านใหม่</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[640px] text-left">
                        <thead className="text-[11px] text-[#716F6A]">
                          <tr>
                            <th className="px-6 py-4 font-normal">รหัสวิชา</th>
                            <th className="px-6 py-4 font-normal">ชื่อรายวิชา</th>
                            <th className="px-6 py-4 font-normal">หน่วยกิต</th>
                            <th className="px-6 py-4 font-normal">เกรด</th>
                            <th className="px-6 py-4 font-normal">สถานะ</th>
                          </tr>
                        </thead>
                        {semesters.map((semester, s) => (
                          <tbody key={s} className="text-[13px]">
                            <tr className="bg-[#F8F7F5] border-t border-[#E7E4DE]">
                              <td colSpan={5} className="px-6 py-2 text-[12px] font-semibold">
                                ภาค {semester.sem_num ?? "—"} / ปีการศึกษา {semester.year ?? "—"}
                                <span className="font-normal text-[#716F6A]"> · GPA {semester.GPA || "—"} · {semester.subject?.length || 0} วิชา</span>
                              </td>
                            </tr>
                            {(semester.subject || []).map((course, r) => {
                              const rowIssues = courseIssues(s, r);
                              return (
                                <tr key={r} className="border-t border-[#E7E4DE]">
                                  <td className="px-6 py-4 font-mono">{course.subject_id || "—"}</td>
                                  <td className="px-6 py-4">{course.subject_name || "—"}</td>
                                  <td className="px-6 py-4">{course.credit ?? "—"}</td>
                                  <td className="px-6 py-4 font-semibold">{course.grade_earn?.toUpperCase() || "—"}</td>
                                  <td className="px-6 py-3">
                                    <span title={rowIssues.map(issue => issue.message).join("\n") || undefined} className={`inline-flex items-center h-[26px] px-3 border rounded-[13px] text-[10px] ${rowIssues.length ? "border-amber-200 bg-amber-50 text-[#A96519]" : "border-[#E7E4DE] text-[#3E8D67]"}`}>
                                      {rowIssues.length ? "ตรวจสอบ" : "ผ่าน"}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        ))}
                      </table>
                    </div>
                  )}
                </div>
              </div>

              <div className="w-full xl:w-[320px] flex-shrink-0 flex flex-col gap-6">
                {issues.length > 0 && (
                  <div className="bg-white border border-[#E7E4DE] rounded-[22px] p-6 shadow-sm">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-7 h-7 border border-[#E7E4DE] rounded-[14px] flex items-center justify-center text-[#A96519] font-bold">!</div>
                      <div className="text-[14px] font-semibold">พบ {issues.length} รายการที่ควรตรวจสอบ</div>
                    </div>
                    <ul className="max-h-[260px] overflow-y-auto space-y-3 mb-4">
                      {issues.map((issue, i) => (
                        <li key={i} className="text-[12px]">
                          <div className={issue.severity === "error" ? "text-red-600 font-semibold" : "text-[#A96519] font-semibold"}>{describePath(issue.path, semesters)}</div>
                          <div className="text-[#716F6A]">{issue.message}</div>
                        </li>
                      ))}
                    </ul>
                    <button className="text-[12px] text-[#F47721] font-semibold hover:underline" onClick={() => setShowJsonEditor(true)}>แก้ไขใน JSON editor →</button>
                  </div>
                )}

                <div className="bg-white border border-[#E7E4DE] rounded-[22px] p-6 shadow-sm">
                  <div className="flex justify-between items-center mb-4">
                    <div className="text-[14px] font-semibold">รายวิชาที่ผ่านการตรวจ</div>
                    <div className={`text-[14px] font-semibold ${passRate === 100 ? "text-[#3E8D67]" : "text-[#F47721]"}`}>{courses ? passRate + "%" : "—"}</div>
                  </div>
                  <div className="h-2 bg-[#E7E4DE] rounded-full overflow-hidden mb-4">
                    <div className={`h-full rounded-full ${passRate === 100 ? "bg-[#3E8D67]" : "bg-[#F47721]"}`} style={{ width: passRate + "%" }}></div>
                  </div>
                  <dl className="text-[12px] text-[#716F6A] grid grid-cols-2 gap-y-1">
                    <dt>ผ่าน / ทั้งหมด</dt><dd className="text-right text-[#292825]">{courses - flaggedCourses} / {courses}</dd>
                    <dt>ข้อผิดพลาด</dt><dd className="text-right text-[#292825]">{current.validation?.errors ?? 0}</dd>
                    <dt>คำเตือน</dt><dd className="text-right text-[#292825]">{current.validation?.warnings ?? 0}</dd>
                    <dt>วิธีอ่าน</dt><dd className="text-right text-[#292825]">{current.engine || "—"}</dd>
                    <dt>ชนิดไฟล์</dt><dd className="text-right text-[#292825]">{fileExtension(current.filename).slice(1).toUpperCase() || "—"}</dd>
                    <dt>เวลาประมวลผล</dt><dd className="text-right text-[#292825]">{current.processing_seconds.toFixed(2)} วินาที</dd>
                  </dl>
                  {edited && <div className="mt-4 text-[11px] text-[#A96519]">ผลตรวจนี้อ้างอิงข้อมูลตอนอ่าน OCR ยังไม่รวมการแก้ไขใน JSON editor</div>}
                </div>

                <div className="bg-white border border-[#E7E4DE] rounded-[18px] p-6 shadow-sm">
                  <div className="flex justify-between items-center mb-3">
                    <div className="text-[16px] font-semibold">{"{ }"} JSON editor</div>
                    {edited && <span className="text-[10px] px-2 py-1 rounded-full bg-amber-50 text-[#A96519] border border-amber-200">แก้ไขแล้ว</span>}
                  </div>
                  <div className="text-[12px] text-[#716F6A] mb-4 leading-relaxed">แก้ไขข้อมูลดิบได้ทุกฟิลด์ ตารางด้านซ้ายจะเปลี่ยนตามทันที</div>
                  <button onClick={() => setShowJsonEditor(!showJsonEditor)} className="text-[12px] font-semibold text-[#F47721] hover:underline">
                    {showJsonEditor ? "ซ่อน JSON editor" : "เปิด JSON editor →"}
                  </button>
                  {showJsonEditor && (
                    <div className="mt-4">
                      <textarea
                        aria-label="แก้ไขผล OCR ในรูป JSON"
                        spellCheck={false}
                        value={editor}
                        onChange={e => updateEditor(e.target.value)}
                        className="w-full h-96 resize-y bg-slate-900 text-slate-100 rounded-xl p-4 font-mono text-xs border border-slate-700 focus:outline-none focus:border-[#F47721]"
                      />
                      {jsonError && <div className="text-red-500 text-xs mt-2">{jsonError}</div>}
                      <div className="flex gap-4 mt-3 text-[12px] font-semibold">
                        <button onClick={formatJson} disabled={!!jsonError} className="text-[#F47721] hover:underline disabled:opacity-40">จัดรูปแบบ</button>
                        <button onClick={() => updateEditor(JSON.stringify(current.record, null, 2))} disabled={!edited && !jsonError} className="text-[#716F6A] hover:underline disabled:opacity-40">คืนค่าผล OCR เดิม</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {currentTab === "search" && (
            <div className="max-w-[960px]">
              <div className="text-[28px] font-semibold mb-2">ค้นหาผลการเรียน</div>
              <div className="text-[14px] text-[#716F6A] mb-8 font-semibold">ค้นหาผลการเรียนที่บันทึกไว้ในฐานข้อมูล</div>

              <form onSubmit={search} className="bg-white border border-[#E7E4DE] rounded-[24px] p-6 lg:p-8 shadow-sm mb-8 grid sm:grid-cols-[1fr_1fr_auto] gap-4 items-start">
                <SuggestInput label="รหัสนักศึกษา" kind="student" digits={8} placeholder="เช่น 67070127" value={studentId} onChange={setStudentId} />
                <SuggestInput label="รหัสวิชา (ไม่บังคับ)" kind="subject" digits={8} placeholder="เช่น 01006001" value={subjectId} onChange={setSubjectId} />
                <button type="submit" disabled={busy} className="h-[44px] sm:mt-[26px] px-6 bg-[#F47721] text-white rounded-[14px] text-[14px] font-medium hover:bg-orange-600 disabled:opacity-50">
                  {busy ? "กำลังค้นหา..." : "ค้นหา"}
                </button>
              </form>

              {searched && grades.length === 0 && (
                <div className="bg-white border border-[#E7E4DE] rounded-[22px] p-8 text-center text-[14px] text-[#716F6A]">
                  ไม่พบผลการเรียนที่ตรงกับเงื่อนไข ตรวจสอบรหัสอีกครั้ง หรือบันทึก transcript ของนักศึกษาคนนี้ก่อน
                </div>
              )}

              {grades.length > 0 && (
                <div className="bg-white border border-[#E7E4DE] rounded-[22px] shadow-sm overflow-hidden">
                  <div className="p-6 border-b border-[#E7E4DE] text-[16px] font-semibold">ผลการค้นหา ({grades.length} รายการ)</div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[600px] text-left text-[13px]">
                      <thead className="bg-[#F8F7F5] text-[11px] text-[#716F6A] border-b border-[#E7E4DE]">
                        <tr>
                          <th className="px-6 py-4 font-normal">รหัสนักศึกษา</th>
                          <th className="px-6 py-4 font-normal">ภาค/ปี</th>
                          <th className="px-6 py-4 font-normal">รหัสวิชา</th>
                          <th className="px-6 py-4 font-normal">ชื่อรายวิชา</th>
                          <th className="px-6 py-4 font-normal">เกรด</th>
                        </tr>
                      </thead>
                      <tbody>
                        {grades.map((grade, idx) => (
                          <tr key={idx} className="border-b border-[#E7E4DE] last:border-0">
                            <td className="px-6 py-4 font-mono">{grade.student_id}</td>
                            <td className="px-6 py-4">{grade.semester_number}/{grade.academic_year}</td>
                            <td className="px-6 py-4 font-mono">{grade.subject_id}</td>
                            <td className="px-6 py-4">{grade.subject_name}</td>
                            <td className="px-6 py-4 font-semibold text-[14px]">{grade.grade?.toUpperCase() || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {guideOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setGuideOpen(false)}>
          <div role="dialog" aria-modal="true" aria-labelledby="guide-title" className="w-full max-w-[560px] max-h-[90vh] overflow-y-auto bg-white rounded-[22px] p-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <div id="guide-title" className="text-[18px] font-semibold">Checklist เตรียมเอกสารให้ OCR อ่านแม่นยำ</div>
              <button onClick={() => setGuideOpen(false)} aria-label="ปิด" className="text-[#716F6A] hover:text-[#292825]">✕</button>
            </div>
            <div className="space-y-5 text-[13px]">
              <section>
                <div className="font-semibold mb-2">ไฟล์ที่แนะนำ</div>
                <ul className="list-disc pl-5 space-y-1 text-[#4A4843]">
                  <li>ใช้ PDF ต้นฉบับจากระบบทะเบียนก่อนเสมอ อ่านได้เร็วและแม่นที่สุด</li>
                  <li>ถ้าเป็น PDF ที่สแกนจากกระดาษ ให้ติ๊ก “บังคับอ่านด้วย OCR”</li>
                  <li>รองรับ PDF, PNG, JPG, TIFF, HEIC ขนาดไม่เกิน 20 MB ต่อไฟล์</li>
                </ul>
              </section>
              <section>
                <div className="font-semibold mb-2">ถ้าต้องถ่ายภาพ</div>
                <ul className="list-disc pl-5 space-y-1 text-[#4A4843]">
                  <li>วางเอกสารบนพื้นเรียบสีเข้ม ให้เห็นมุมกระดาษครบทั้ง 4 มุม</li>
                  <li>ถือกล้องขนานกับกระดาษ ไม่เอียง ไม่กลับหัว</li>
                  <li>ใช้แสงสม่ำเสมอ หลีกเลี่ยงเงามือและแสงสะท้อนจากไฟหรือแฟลช</li>
                  <li>ให้หน้ากระดาษกว้างอย่างน้อย 1500 พิกเซล ภาพที่เล็กกว่า 900 พิกเซลจะอ่านตารางได้ไม่ชัด</li>
                  <li>ถ่ายหนึ่งหน้าต่อหนึ่งภาพ และอย่าครอปหัวกระดาษหรือตารางออก</li>
                </ul>
              </section>
              <section>
                <div className="font-semibold mb-2">หลังอ่านเสร็จ</div>
                <ul className="list-disc pl-5 space-y-1 text-[#4A4843]">
                  <li>รายวิชาที่ขึ้นสถานะ “ตรวจสอบ” ให้เทียบกับเอกสารจริง แล้วแก้ใน JSON editor</li>
                  <li>ถ้าระบบตรวจรูปแบบผิด ให้เลือก “รูปแบบเอกสาร” เองแล้วอ่านใหม่</li>
                </ul>
              </section>
            </div>
          </div>
        </div>
      )}

      {cameraStream && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div role="dialog" aria-modal="true" className="w-full max-w-[520px] max-h-[96vh] overflow-y-auto bg-white rounded-[22px] p-5">
            <div className="text-[16px] font-semibold mb-1">ถ่ายรูป Transcript</div>
            <div className="text-[12px] text-[#716F6A] mb-3">วางกระดาษแนวตั้งให้พอดีกรอบ เห็นครบทั้งหน้า แสงสม่ำเสมอ และไม่มีเงา</div>
            <div className="relative mx-auto rounded-xl overflow-hidden bg-black" style={{ aspectRatio: String(PAGE_RATIO), width: "min(100%, calc(62vh * " + PAGE_RATIO + "))" }}>
              <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover" />
              <div className="pointer-events-none absolute inset-3 rounded-md border-2 border-dashed border-white/70"></div>
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setCameraStream(null)} className="h-[44px] px-6 border border-[#E7E4DE] rounded-[14px] text-[13px] hover:bg-slate-50">ยกเลิก</button>
              <button onClick={capturePhoto} className="h-[44px] px-6 bg-[#F47721] text-white rounded-[14px] text-[13px] font-medium hover:bg-orange-600">ถ่ายและอ่านข้อมูล</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
