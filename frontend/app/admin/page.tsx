"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/Header";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Layers,
  Database,
  Calendar,
} from "lucide-react";

interface DocumentStatusItem {
  document_id: string;
  filename: string;
  title: string;
  status: string;
  chunks_count: number;
  uploaded_at: string;
}

export default function AdminOnboardingPage() {
  const [documents, setDocuments] = useState<DocumentStatusItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  async function fetchDocuments() {
    setIsLoadingDocs(true);
    try {
      const res = await fetch("/api/onboarding/documents");
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      } else {
        console.error("Failed to fetch documents list");
      }
    } catch (err) {
      console.error("Error fetching documents:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  }

  useEffect(() => {
    fetchDocuments();
  }, []);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    setStatusMessage(null);
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) {
      setStatusMessage({
        type: "error",
        text: "Please select a document file first.",
      });
      return;
    }

    setIsUploading(true);
    setStatusMessage(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch("/api/onboarding/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        let errText = "Upload failed. Please try again.";
        try {
          const errData = await res.json();
          if (typeof errData.detail === "string") errText = errData.detail;
        } catch {
          // ignore
        }
        throw new Error(errText);
      }

      const result: DocumentStatusItem = await res.json();
      setStatusMessage({
        type: "success",
        text: `Document "${result.filename}" successfully uploaded and ingested into Azure AI Search (${result.chunks_count} chunks).`,
      });

      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // Automatically refresh document list after upload
      await fetchDocuments();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      setStatusMessage({
        type: "error",
        text: msg,
      });
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="flex h-full flex-1 flex-col bg-[var(--color-canvas)]">
      <Header />

      <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
        <div className="mx-auto max-w-4xl space-y-8">
          {/* Page Header */}
          <div className="border-b border-[var(--color-border)] pb-5">
            <h2
              className="text-2xl font-semibold tracking-tight text-[var(--color-ink)]"
              style={{ fontFamily: "var(--font-stack-serif)" }}
            >
              Document Onboarding Pipeline
            </h2>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Upload company HR & IT policies to chunk, embed, and index into Azure AI Search for live agent retrieval.
            </p>
          </div>

          {/* Upload Card */}
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-xs">
            <div className="flex items-center gap-2.5 border-b border-[var(--color-border)] pb-4 mb-5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-seal-soft)] text-[var(--color-seal)]">
                <UploadCloud className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-base font-medium text-[var(--color-ink)]">
                  Upload New Policy Document
                </h3>
                <p className="text-xs text-[var(--color-muted)]">
                  Supported formats: Markdown (.md), Text (.txt), PDF (.pdf)
                </p>
              </div>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
                <label className="flex-1 flex items-center gap-3 cursor-pointer rounded-xl border border-dashed border-[var(--color-border-strong)] bg-[var(--color-canvas)] px-4 py-3 hover:border-[var(--color-seal)] transition-colors">
                  <FileText className="h-5 w-5 text-[var(--color-muted)] shrink-0" />
                  <span className="text-sm font-medium text-[var(--color-ink)] truncate">
                    {selectedFile ? selectedFile.name : "Choose a policy document..."}
                  </span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".md,.txt,.pdf,.docx"
                    onChange={handleFileSelect}
                    className="sr-only"
                  />
                </label>

                <button
                  type="submit"
                  disabled={isUploading || !selectedFile}
                  className="flex items-center justify-center gap-2 rounded-xl bg-[var(--color-ink)] px-6 py-3 text-sm font-medium text-white shadow-xs hover:bg-[var(--color-ink-soft)] disabled:opacity-50 disabled:cursor-not-allowed transition-all shrink-0 cursor-pointer"
                >
                  {isUploading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Uploading & Ingesting...
                    </>
                  ) : (
                    <>
                      <UploadCloud className="h-4 w-4" />
                      Upload Document
                    </>
                  )}
                </button>
              </div>

              {/* Status Message */}
              {statusMessage && (
                <div
                  className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-xs font-medium transition-all ${
                    statusMessage.type === "success"
                      ? "border-[var(--color-seal)]/30 bg-[var(--color-seal-soft)] text-[var(--color-seal)]"
                      : "border-[var(--color-flag-border)] bg-[var(--color-flag-surface)] text-[var(--color-flag)]"
                  }`}
                >
                  {statusMessage.type === "success" ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  )}
                  <span>{statusMessage.text}</span>
                </div>
              )}
            </form>
          </div>

          {/* Ingested Documents Table */}
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-paper)] p-6 shadow-xs">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-4 mb-5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-canvas)] text-[var(--color-ink)]">
                  <Database className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-base font-medium text-[var(--color-ink)]">
                    Ingested Knowledge Documents
                  </h3>
                  <p className="text-xs text-[var(--color-muted)]">
                    Documents active in the Azure AI Search index ({documents.length} total)
                  </p>
                </div>
              </div>

              <button
                onClick={fetchDocuments}
                disabled={isLoadingDocs}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)] rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
                title="Refresh document list"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoadingDocs ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            {isLoadingDocs ? (
              <div className="py-12 text-center text-sm text-[var(--color-muted)]">
                Loading ingested documents...
              </div>
            ) : documents.length === 0 ? (
              <div className="py-12 text-center text-sm text-[var(--color-muted)]">
                No policy documents indexed yet. Upload one above.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-muted)] font-medium">
                      <th className="pb-3 pt-1 px-3">Document Title / File</th>
                      <th className="pb-3 pt-1 px-3">Status</th>
                      <th className="pb-3 pt-1 px-3">Chunks</th>
                      <th className="pb-3 pt-1 px-3">Uploaded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {documents.map((doc) => (
                      <tr key={doc.filename} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                        <td className="py-3 px-3">
                          <div className="font-medium text-[var(--color-ink)] text-sm">
                            {doc.title}
                          </div>
                          <div className="text-[11px] font-mono text-[var(--color-muted)]">
                            {doc.filename}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-seal-soft)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--color-seal)] border border-[var(--color-seal)]/20">
                            <CheckCircle2 className="h-3 w-3" />
                            {doc.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="inline-flex items-center gap-1 font-mono text-xs text-[var(--color-ink-soft)]">
                            <Layers className="h-3 w-3 text-[var(--color-muted)]" />
                            {doc.chunks_count} chunks
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[var(--color-muted)]">
                          <span className="inline-flex items-center gap-1 text-[11px]">
                            <Calendar className="h-3 w-3" />
                            {new Date(doc.uploaded_at).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
