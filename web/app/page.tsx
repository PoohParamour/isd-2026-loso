"use client";

import { useState } from "react";

type Course = { subject_id?: string; subject_name?: string; credit?: number; grade_earn?: string };
type Semester = { year?: number; sem_num?: number; GPA?: string; subject?: Course[] };
type RecordData = {
  format_id?: string;
  header_detail?: { student_id?: string; prename?: string; name?: string; program?: string };
  transcript_detail?: { semesters?: Semester[]; total_credits_earned?: number; cumulative_gpa?: string };
};
type Extraction = { filename: string; engine: string; processing_seconds: number; record: RecordData; error?: string };
type Grade = { student_id: string; academic_year: string; semester_number: string; subject_id: string; subject_name: string; grade: string };

async function api(path: string, init?: RequestInit) {
  const response = await fetch("/api/proxy/" + path, { cache: "no-store", ...init });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "HTTP " + response.status);
  return data;
}

const formatOptions = [
  ["auto", "ตรวจรูปแบบอัตโนมัติ"],
  ["bachelor_th", "ปริญญาตรี · ไทย"],
  ["bachelor_en", "ปริญญาตรี · อังกฤษ"],
  ["graduate_th", "บัณฑิตศึกษา · ไทย"],
  ["graduate_en", "บัณฑิตศึกษา · อังกฤษ"],
];

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [format, setFormat] = useState("auto");
  const [forceOcr, setForceOcr] = useState(false);
  const [results, setResults] = useState<Extraction[]>([]);
  const [selected, setSelected] = useState(0);
  const [editor, setEditor] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [progress, setProgress] = useState("");
  const [studentId, setStudentId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [grades, setGrades] = useState<Grade[]>([]);

  const current = results[selected];
  let record: RecordData | undefined;
  let jsonError = "";
  if (current && !current.error) {
    try { record = JSON.parse(editor) as RecordData; }
    catch { jsonError = "JSON ไม่ถูกต้อง กรุณาตรวจวงเล็บและเครื่องหมาย"; }
  }
  const semesters = record?.transcript_detail?.semesters || [];
  const courses = semesters.reduce((count, semester) => count + (semester.subject?.length || 0), 0);

  async function extractAll() {
    if (!files.length) return;
    setBusy(true); setMessage(""); setResults([]); setSelected(0);
    const next: Extraction[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        setProgress("กำลังอ่าน " + (i + 1) + "/" + files.length + ": " + files[i].name);
        const form = new FormData();
        form.append("file", files[i]);
        if (format !== "auto") form.append("format_id", format);
        if (forceOcr) form.append("force_ocr", "true");
        try {
          const value = await api("transcripts/extract", { method: "POST", body: form }) as Extraction;
          next.push(value);
          if (next.length === 1) setEditor(JSON.stringify(value.record, null, 2));
        } catch (error) {
          next.push({ filename: files[i].name, engine: "", processing_seconds: 0, record: {}, error: String(error) });
        }
        setResults([...next]);
      }
      const passed = next.filter(item => !item.error);
      const seconds = passed.reduce((sum, item) => sum + item.processing_seconds, 0);
      setMessage("อ่านสำเร็จ " + passed.length + "/" + next.length + " ฉบับ · เวลา OCR รวม " + seconds.toFixed(2) + " วินาที");
    } finally { setBusy(false); setProgress(""); }
  }

  function select(index: number) {
    setSelected(index);
    setEditor(JSON.stringify(results[index].record, null, 2));
    setMessage("");
  }

  async function save() {
    if (!current || !record || jsonError) return;
    setBusy(true); setMessage("");
    try {
      const result = await api("documents", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: current.filename, record, engine: current.engine, processing_seconds: current.processing_seconds }),
      });
      setMessage("บันทึกแล้ว · รหัสเอกสาร " + result.document_id);
    } catch (error) { setMessage("บันทึกไม่สำเร็จ: " + String(error)); }
    finally { setBusy(false); }
  }

  async function search() {
    if (!studentId.trim() && !subjectId.trim()) { setMessage("กรอกรหัสนักศึกษาหรือรหัสวิชา"); return; }
    setBusy(true); setMessage("");
    try {
      const params = new URLSearchParams();
      if (studentId.trim()) params.set("student_id", studentId.trim());
      if (subjectId.trim()) params.set("subject_id", subjectId.trim());
      const result = await api("grades?" + params.toString());
      setGrades(result.results || []);
      setMessage("พบผลการเรียน " + result.count + " รายการ");
    } catch (error) { setMessage("ค้นหาไม่สำเร็จ: " + String(error)); }
    finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-5">
        <div><p className="text-xs font-bold uppercase tracking-[.2em] text-orange-600">KMITL · Intelligent System Development</p><h1 className="mt-1 text-2xl font-bold">Transcript OCR Studio</h1></div>
        <span className="rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-600">อ่าน · ตรวจ · บันทึก · ค้นเกรด</span>
      </div>
    </header>
    <div className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="space-y-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">1. นำเข้า Transcript</h2>
          <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-orange-300 bg-orange-50 px-4 text-center hover:bg-orange-100">
            <span className="text-3xl text-orange-600">↑</span><span className="mt-2 font-medium">เลือกไฟล์เพื่ออ่านแบบชุด</span>
            <span className="mt-1 text-xs text-slate-500">PDF, PNG, JPG, TIFF · ไม่เกิน 20 MB ต่อไฟล์</span>
            <input aria-label="เลือกไฟล์ Transcript" className="sr-only" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff" onChange={event => setFiles(Array.from(event.target.files || []))} />
          </label>
          {files.length > 0 && <div className="mt-3 max-h-32 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{files.map((file, index) => <div className="truncate py-0.5" key={index}>{file.name}</div>)}</div>}
          <label className="mt-4 block text-sm font-medium">รูปแบบเอกสาร</label>
          <select className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2.5 text-sm" value={format} onChange={event => setFormat(event.target.value)}>{formatOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <label className="mt-4 flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={forceOcr} onChange={event => setForceOcr(event.target.checked)} />บังคับอ่านภาพ OCR</label>
          <button disabled={busy || !files.length} onClick={extractAll} className="mt-5 w-full rounded-lg bg-orange-600 px-4 py-3 font-semibold text-white hover:bg-orange-700 disabled:opacity-50">เริ่มอ่าน {files.length || ""} ไฟล์</button>
          {progress && <p role="status" className="mt-3 text-sm text-orange-700">{progress}</p>}
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">2. ค้นผลการเรียน</h2>
          <input aria-label="รหัสนักศึกษา" placeholder="รหัสนักศึกษา" value={studentId} onChange={event => setStudentId(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
          <input aria-label="รหัสวิชา" placeholder="รหัสวิชา (ถ้ามี)" value={subjectId} onChange={event => setSubjectId(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
          <button onClick={search} disabled={busy} className="mt-3 w-full rounded-lg border border-slate-300 px-4 py-2.5 font-medium hover:bg-slate-50 disabled:opacity-50">ค้นหาในฐานข้อมูล</button>
        </section>
      </aside>
      <div className="min-w-0 space-y-6">
        {message && <div role="status" className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">{message}</div>}
        {results.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="mb-3 font-semibold">ผลการอ่านแบบชุด</h2><div className="flex flex-wrap gap-2">{results.map((item, index) => <button key={index} onClick={() => select(index)} className={"rounded-lg border px-3 py-2 text-left text-sm " + (selected === index ? "border-orange-500 bg-orange-50" : "border-slate-200 hover:bg-slate-50")}><span className="block max-w-48 truncate font-medium">{item.filename}</span><span className={item.error ? "text-red-600" : "text-slate-500"}>{item.error ? "อ่านไม่สำเร็จ" : item.processing_seconds + " วินาที · " + item.record.format_id}</span></button>)}</div></section>}
        {current?.error && <section className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">{current.error}</section>}
        {current && !current.error && <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-widest text-orange-600">ตรวจข้อมูลก่อนบันทึก</p><h2 className="mt-1 text-xl font-bold">{current.filename}</h2><p className="mt-1 text-sm text-slate-500">{current.engine} · {current.processing_seconds} วินาที · {record?.format_id}</p></div><button onClick={save} disabled={busy || !!jsonError} className="rounded-lg bg-slate-900 px-5 py-2.5 font-semibold text-white hover:bg-slate-700 disabled:opacity-50">บันทึกผลที่ตรวจแล้ว</button></div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[["รหัสนักศึกษา", record?.header_detail?.student_id], ["ชื่อ-สกุล", (record?.header_detail?.prename || "") + " " + (record?.header_detail?.name || "")], ["หลักสูตร", record?.header_detail?.program], ["GPA สะสม", record?.transcript_detail?.cumulative_gpa]].map(([label, value]) => <div className="rounded-xl bg-slate-50 p-4" key={label}><div className="text-xs text-slate-500">{label}</div><div className="mt-2 break-words font-semibold">{value || "—"}</div></div>)}</div>
            <p className="mt-4 text-sm text-slate-500">{semesters.length} ภาคการศึกษา · {courses} รายวิชา · {record?.transcript_detail?.total_credits_earned ?? "—"} หน่วยกิต</p>
          </section>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="mb-4 text-lg font-semibold">รายวิชาที่อ่านได้</h2><div className="max-h-[460px] overflow-auto">{semesters.map((semester, index) => <div className="mb-5" key={index}><h3 className="mb-2 rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold">ภาค {semester.sem_num ?? "—"} · ปี {semester.year ?? "—"} · GPA {semester.GPA || "—"}</h3><table className="w-full min-w-[520px] text-left text-sm"><thead className="text-xs text-slate-500"><tr><th className="p-2">รหัส</th><th className="p-2">รายวิชา</th><th className="p-2">หน่วยกิต</th><th className="p-2">เกรด</th></tr></thead><tbody>{(semester.subject || []).map((course, courseIndex) => <tr className="border-t border-slate-100" key={courseIndex}><td className="p-2 font-mono">{course.subject_id || "—"}</td><td className="p-2">{course.subject_name || "—"}</td><td className="p-2">{course.credit ?? "—"}</td><td className="p-2 font-semibold">{course.grade_earn || "—"}</td></tr>)}</tbody></table></div>)}</div></section>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold">แก้ไขข้อมูล JSON</h2><p className="mb-3 text-sm text-slate-500">ตรวจและแก้ทุกฟิลด์ก่อนบันทึก ตารางด้านบนจะเปลี่ยนตามข้อมูล</p><textarea aria-label="แก้ไขผล OCR ในรูป JSON" spellCheck={false} value={editor} onChange={event => setEditor(event.target.value)} className="h-80 w-full resize-y rounded-lg border border-slate-300 bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-100" />{jsonError && <p className="mt-2 text-sm text-red-600">{jsonError}</p>}</section>
        </>}
        {grades.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="mb-3 text-lg font-semibold">ผลการค้นหา</h2><div className="overflow-x-auto"><table className="w-full min-w-[580px] text-left text-sm"><thead><tr className="bg-slate-100"><th className="p-3">นักศึกษา</th><th className="p-3">ภาค</th><th className="p-3">รหัสวิชา</th><th className="p-3">ชื่อวิชา</th><th className="p-3">เกรด</th></tr></thead><tbody>{grades.map((grade, index) => <tr className="border-t border-slate-100" key={index}><td className="p-3">{grade.student_id}</td><td className="p-3">{grade.semester_number}/{grade.academic_year}</td><td className="p-3 font-mono">{grade.subject_id}</td><td className="p-3">{grade.subject_name}</td><td className="p-3 font-bold">{grade.grade}</td></tr>)}</tbody></table></div></section>}
        {!current && grades.length === 0 && <section className="flex min-h-80 flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm"><div className="mb-4 text-5xl">▤</div><h2 className="text-xl font-semibold">เริ่มจากอัปโหลด Transcript</h2><p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">อ่าน PDF หรือภาพ ตรวจข้อมูลที่สกัดได้ บันทึก และค้นเกรดรายวิชา</p></section>}
      </div>
    </div>
  </main>;
}
