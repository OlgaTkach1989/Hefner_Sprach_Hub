import { useState } from "react";

import Editor from "@monaco-editor/react";

import { askStudentLessonAi, checkStudentLessonCode } from "../../api/onlineStudentApi";
import type { InteractiveLessonStep, StudentLessonGraderResponse } from "../../types";

type Props = {
  lessonId: number;
  step: InteractiveLessonStep;
  completed: boolean;
  onPassed: () => void;
};

export const LessonCodePractice = ({ lessonId, step, completed, onPassed }: Props) => {
  const [code, setCode] = useState(step.starterCode || "");
  const [result, setResult] = useState<StudentLessonGraderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [showSolution, setShowSolution] = useState(false);
  const [aiAnswer, setAiAnswer] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  const runCheck = async () => {
    setLoading(true);
    setResult(null);

    try {
      const data = await checkStudentLessonCode(lessonId, {
        stepId: step.id,
        code,
      });
      setResult(data);
      if (data.status === "success") {
        onPassed();
      }
    } catch {
      setResult({
        status: "error",
        message: "Could not reach the lesson grader API.",
        checks: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const askAI = async () => {
    setAiLoading(true);
    try {
      const data = await askStudentLessonAi(lessonId, {
        stepId: step.id,
        question: "Explain what is wrong or what should be improved in this code.",
        code,
      });
      setAiAnswer(data.answer);
    } catch {
      setAiAnswer("Could not reach the lesson AI endpoint.");
    } finally {
      setAiLoading(false);
    }
  };

  const cardClass =
    result?.status === "success"
      ? "lesson-workspace__grader-card lesson-workspace__grader-card--success"
      : result?.status === "fail"
        ? "lesson-workspace__grader-card lesson-workspace__grader-card--fail"
        : "lesson-workspace__grader-card lesson-workspace__grader-card--error";

  return (
    <div className="lesson-workspace__code-stack">
      <div className="lesson-workspace__code-head">
        <div>
          <div className="lesson-workspace__eyebrow">Practice</div>
          <div className="lesson-workspace__editor-tag">Monaco + lesson grader</div>
        </div>
        {completed ? <div className="lesson-workspace__status-pill is-complete">Completed</div> : null}
      </div>

      <div className="lesson-workspace__editor-frame">
        <div className="lesson-workspace__editor-head">
          <span>student.py</span>
          <span>Runs against the lesson grader endpoint</span>
        </div>
        <Editor
          height="340px"
          defaultLanguage="python"
          value={code}
          onChange={(value) => setCode(value || "")}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            roundedSelection: true,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: "on",
            padding: { top: 16 },
          }}
        />
      </div>

      <div className="lesson-workspace__action-row">
        <button type="button" onClick={() => void runCheck()} disabled={loading} className="lesson-workspace__primary-button">
          {loading ? "Checking..." : "Run & Check"}
        </button>

        <button
          type="button"
          onClick={() => {
            setCode(step.starterCode || "");
            setResult(null);
            setAiAnswer("");
          }}
          className="lesson-workspace__secondary-button"
        >
          Reset
        </button>

        {step.hint ? (
          <button type="button" onClick={() => setShowHint((prev) => !prev)} className="lesson-workspace__secondary-button">
            {showHint ? "Hide hint" : "Show hint"}
          </button>
        ) : null}

        {step.solution ? (
          <button
            type="button"
            onClick={() => setShowSolution((prev) => !prev)}
            className="lesson-workspace__secondary-button"
          >
            {showSolution ? "Hide solution" : "Show solution"}
          </button>
        ) : null}

        <button type="button" onClick={() => void askAI()} disabled={aiLoading} className="lesson-workspace__secondary-button">
          {aiLoading ? "Asking AI..." : "Ask AI"}
        </button>
      </div>

      {showHint && step.hint ? (
        <div className="lesson-workspace__feedback-card">
          <strong>Hint</strong>
          <p>{step.hint}</p>
        </div>
      ) : null}

      {showSolution && step.solution ? (
        <div className="lesson-workspace__feedback-card">
          <strong>Solution</strong>
          <pre className="lesson-workspace__markdown__code">
            <code>{step.solution}</code>
          </pre>
        </div>
      ) : null}

      {aiAnswer ? (
        <div className="lesson-workspace__feedback-card lesson-workspace__feedback-card--ai">
          <strong>AI explanation</strong>
          <p>{aiAnswer}</p>
        </div>
      ) : null}

      {result ? (
        <div className={cardClass}>
          <strong>{result.message}</strong>
          {result.checks.length > 0 ? (
            <div className="lesson-workspace__grader-checks">
              {result.checks.map((check) => (
                <div key={check.name} className="lesson-workspace__grader-check">
                  <div className="lesson-workspace__grader-check-name">
                    {check.passed ? "PASS" : "FAIL"} · {check.name}
                  </div>
                  {check.expected ? (
                    <div className="lesson-workspace__grader-check-meta">
                      Expected: <code>{check.expected}</code>
                    </div>
                  ) : null}
                  {check.actual ? (
                    <div className="lesson-workspace__grader-check-meta">
                      Actual: <code>{check.actual}</code>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default LessonCodePractice;
