import React, { useState } from "react";
import axios from "axios";
import { Button, Typography, Container, Box, Card } from "@mui/material";

const PiiRedactionApp = () => {
  const [pdf, setPdf] = useState(null);
  const [redactedPdf, setRedactedPdf] = useState(null);
  const [usedOcr, setUsedOcr] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleUpload = (event) => {
    setPdf(event.target.files[0]);
  };

  const handleRedact = async () => {
    if (!pdf) {
      alert("Please upload a PDF first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", pdf);
    setIsLoading(true);

    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/redact-pdf/",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      if (response.status === 200 && response.data.filename) {
        setRedactedPdf(`http://127.0.0.1:8000/output/${response.data.filename}`);
        setUsedOcr(response.data.used_ocr); // Capture OCR info
      } else {
        alert("Something went wrong. Please try again.");
      }
    } catch (error) {
      alert("Failed to process the PDF.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container
      sx={{
        textAlign: "center",
        padding: "20px",
        backgroundColor: "#121212",
        borderRadius: "10px",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {/* Welcome message */}
      <Typography variant="h4" sx={{ fontWeight: "bold", color: "#39ff14", textShadow: "0px 0px 10px #39ff14" }}>
        Welcome to SecurePDF
      </Typography>
      <Typography variant="subtitle1" sx={{ marginBottom: "20px", color: "#a0a0a0" }}>
        The safest way to redact sensitive information from PDFs.
      </Typography>

      {/* Key Features - Wrapped in Card */}
      <Card sx={{ backgroundColor: "#1e1e1e", padding: "15px", borderRadius: "10px", marginBottom: "20px" }}>
        <Typography variant="h6" sx={{ fontWeight: "bold", color: "#39ff14" }}>
          Key Features:
        </Typography>
        <ul style={{ paddingLeft: "20px", color: "#a0a0a0" }}>
          <li>🔐 Secure PII redaction with AI</li>
          <li>⚡ Fast & efficient processing</li>
          <li>📂 Easy file upload & download</li>
          <li>🖥 Seamless API integration</li>
        </ul>
      </Card>

      {/* File upload */}
      <Box sx={{ marginBottom: "15px" }}>
        <input type="file" accept="application/pdf" onChange={handleUpload} style={{ color: "#39ff14" }} />
      </Box>

      <Button
        onClick={handleRedact}
        variant="contained"
        disabled={isLoading}
        sx={{
          backgroundColor: "#39ff14",
          color: "#121212",
          fontWeight: "bold",
          textShadow: "0px 0px 10px #39ff14",
          "&:hover": { backgroundColor: "#2fed06" },
        }}
      >
        {isLoading ? "Processing..." : "Redact PDF"}
      </Button>

      {/* Redacted PDF download link */}
      {redactedPdf && (
        <Box sx={{ marginTop: "20px" }}>
          <Typography sx={{ color: "#39ff14", textShadow: "0px 0px 10px #39ff14" }}>
            ✅ Redacted PDF Ready
          </Typography>
          <Button
            variant="contained"
            href={redactedPdf}
            download
            sx={{
              backgroundColor: "#39ff14",
              color: "#121212",
              fontWeight: "bold",
              textShadow: "0px 0px 10px #39ff14",
              "&:hover": { backgroundColor: "#2fed06" },
            }}
          >
            Download Redacted PDF
          </Button>

          {/* OCR Message */}
          {usedOcr && (
            <Typography sx={{ marginTop: "10px", color: "#ffa726" }}>
              🛈 OCR was used because this PDF appears to be scanned. Accuracy may vary.
            </Typography>
          )}
        </Box>
      )}

      {/* Footer */}
      <Typography variant="body2" sx={{ marginTop: "30px", color: "#a0a0a0" }}>
        Made with ❤ by <span style={{ color: "#39ff14", textShadow: "0px 0px 10px #39ff14" }}>Team Encryptors</span>
      </Typography>
    </Container>
  );
};

export default PiiRedactionApp;
