import { parseDelimited } from "./fileBlocks";

// Plain Blob download -- works for every text-based FileBlock (HTML, XML,
// CSV, JSON, code...) natively, no conversion needed.
export function downloadText(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  downloadBlob(filename, blob);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Deferred, not immediate: revoking synchronously can cut the download
  // off in some browsers before it's actually read the blob URL.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// CSV/TSV -> a real .xlsx, not just a renamed text file -- exceljs is
// dynamically imported so its ~1MB doesn't load for turns that never
// touch this button.
export async function downloadAsExcel(filename: string, content: string, delimiter: string) {
  const ExcelJS = (await import("exceljs")).default;
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Sheet1");
  const rows = parseDelimited(content, delimiter);
  sheet.addRows(rows);
  if (rows.length > 0) {
    sheet.columns.forEach((column) => {
      column.width = 18;
    });
    sheet.getRow(1).font = { bold: true };
  }
  const buffer = await workbook.xlsx.writeBuffer();
  downloadBlob(filename, new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
}
