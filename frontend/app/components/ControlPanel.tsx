"use client";

type ControlPanelProps = {
  cvUploaded: boolean;
  downloadingReport: boolean;
  finalReportReady: boolean;
  loadingCv: boolean;
  onDownloadReport: () => Promise<void>;
  onSelectCv: (file: File | null) => void;
  onUploadCv: () => Promise<void>;
  selectedCvLabel: string;
  copy: {
    kicker: string;
    subtitle: string;
    dragResume: string;
    fileTypes: string;
    browseFiles: string;
    noFileSelected: string;
    uploadCv: string;
    uploading: string;
    cvUploaded: string;
    readyToUpload: string;
    waitingForCv: string;
    opening: string;
    openReportDashboard: string;
  };
};

export function ControlPanel({
  cvUploaded,
  downloadingReport,
  finalReportReady,
  loadingCv,
  onDownloadReport,
  onSelectCv,
  onUploadCv,
  selectedCvLabel,
  copy,
}: ControlPanelProps) {
  const hasSelectedCv = selectedCvLabel !== copy.noFileSelected;

  return (
    <section className="control-panel">
      <div className="control-panel-glow" aria-hidden="true" />
      <div className="panel-copy">
        <div className="section-kicker">{copy.kicker}</div>
        <div className="section-subtitle">{copy.subtitle}</div>
      </div>
      <div className="form">
        <div className="resume-uploader">
          <label className={`resume-dropzone ${hasSelectedCv ? "has-file" : ""}`}>
            <span className="resume-dropzone-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M12 16V6" />
                <path d="M8.5 9.5 12 6l3.5 3.5" />
                <path d="M5 15v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2" />
              </svg>
            </span>
            <span className="resume-dropzone-title">{copy.dragResume}</span>
            <span className="resume-dropzone-button">{copy.browseFiles}</span>
            <span className={`resume-selected ${hasSelectedCv ? "visible" : ""}`}>
              {hasSelectedCv ? selectedCvLabel : copy.noFileSelected}
            </span>
            <span className="file-picker">
              <input
                className="file-picker-input"
                type="file"
                accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
                onChange={(event) => onSelectCv(event.target.files?.[0] || null)}
              />
            </span>
          </label>
          <div className="resume-actions">
            <button
              type="button"
              className="secondary primary-upload"
              disabled={loadingCv || !hasSelectedCv}
              onClick={onUploadCv}
            >
              <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 16V7" />
                <path d="M8.5 10.5 12 7l3.5 3.5" />
                <path d="M6 17v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1" />
              </svg>
              {loadingCv ? copy.uploading : copy.uploadCv}
            </button>
            <span className={`pill resume-pill ${cvUploaded ? "on" : ""}`}>
              {cvUploaded ? copy.cvUploaded : hasSelectedCv ? copy.readyToUpload : copy.waitingForCv}
            </span>
            <button
              type="button"
              className={`secondary report-download ${downloadingReport ? "is-loading" : ""}`}
              disabled={!finalReportReady || downloadingReport}
              onClick={onDownloadReport}
            >
              {downloadingReport ? (
                <span className="button-spinner" aria-hidden="true" />
              ) : (
                <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
                  <path d="M14 3v5h5" />
                  <path d="M12 11v6" />
                  <path d="M9.5 14.5 12 17l2.5-2.5" />
                </svg>
              )}
              {downloadingReport ? copy.opening : copy.openReportDashboard}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

