import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Tab, Tabs } from "@mui/material";
import PageHeader from "../components/PageHeader";
import ResumesTab from "./resume/ResumesTab";
import ProfileTab from "./resume/ProfileTab";
import GeneratedTab from "./resume/GeneratedTab";

export default function MyResume() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") === "generated" ? 2 : 0);
  return (
    <>
      <PageHeader title="My Resume" subtitle="Manage your resume versions, the candidate profile every AI agent works from, and documents generated for specific jobs." />
      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 3, borderBottom: 1, borderColor: "divider" }}>
        <Tab label="Resumes" />
        <Tab label="Candidate profile" />
        <Tab label="Generated documents" />
      </Tabs>
      {tab === 0 && <ResumesTab />}
      {tab === 1 && <ProfileTab />}
      {tab === 2 && <GeneratedTab initialOpenId={params.get("version")} />}
    </>
  );
}
