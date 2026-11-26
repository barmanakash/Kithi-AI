import { useState } from "react";
import { Tab, Tabs } from "@mui/material";
import PageHeader from "../components/PageHeader";
import ChatTab from "../components/coach/ChatTab";
import RoadmapTab from "../components/coach/RoadmapTab";
import ProgressTab from "../components/coach/ProgressTab";
import GithubTab from "../components/coach/GithubTab";
import MemoryTab from "../components/coach/MemoryTab";

const TABS = [
  { key: "chat", label: "Coach chat" },
  { key: "roadmap", label: "Skill gaps & roadmap" },
  { key: "progress", label: "Progress" },
  { key: "github", label: "GitHub portfolio" },
  { key: "memory", label: "My memory" },
];

export default function CareerCoach() {
  const [tab, setTab] = useState("chat");
  return (
    <>
      <PageHeader
        title="AI Career Coach"
        subtitle="Ask questions, close skill gaps, track progress and control what Kithi remembers. Your data and AI stay on this machine."
      />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx={{ mb: 2.5 }}>
        {TABS.map((t) => <Tab key={t.key} value={t.key} label={t.label} />)}
      </Tabs>
      {tab === "chat" && <ChatTab onTab={setTab} />}
      {tab === "roadmap" && <RoadmapTab />}
      {tab === "progress" && <ProgressTab />}
      {tab === "github" && <GithubTab />}
      {tab === "memory" && <MemoryTab />}
    </>
  );
}
