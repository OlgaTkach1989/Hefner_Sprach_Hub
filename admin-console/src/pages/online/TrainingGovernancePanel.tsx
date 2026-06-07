import { useMemo } from "react";

import {
  useGetTrainingAdminAudiencesQuery,
  useGetTrainingAdminContentGovernanceQuery,
  useGetTrainingAdminOverviewQuery,
} from "@/bll/training/training.service";
import type {
  TrainingAdminAudience,
  TrainingContentGovernanceItem,
  TrainingGovernanceFlag,
} from "@/bll/training/training.type";
import TrainingAudienceCrudSection from "./training/TrainingAudienceCrudSection";
import TrainingAiGovernanceSection from "./training/TrainingAiGovernanceSection";
import TrainingCourseRoleCrudSection from "./training/TrainingCourseRoleCrudSection";
import TrainingGrantCrudSection from "./training/TrainingGrantCrudSection";
import cl from "./OnlinePage.module.scss";

const contentKindLabels: Record<TrainingContentGovernanceItem["content_kind"], string> = {
  article: "Article",
  video: "Video",
  notebook: "Notebook",
  faq: "FAQ",
  recording: "Recording",
  exercise: "Exercise",
  dataset: "Dataset",
  link: "External link",
};

const accessScopeLabels: Record<TrainingContentGovernanceItem["access_scope"], string> = {
  public: "Public",
  authenticated: "Authenticated",
  entitled: "Entitled",
};

const governanceFlagLabels: Record<TrainingGovernanceFlag, string> = {
  missing_asset_class: "Missing asset class",
  missing_topic: "Missing topic",
  missing_owner: "Missing owner",
  missing_audience_policy: "Missing audience policy",
  missing_lab_profile: "Missing lab profile",
  lab_profile_incomplete: "Incomplete lab profile",
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

type TrainingGovernancePanelProps = {
  courseId: number;
  courseTitle: string;
  includeAiSection?: boolean;
};

const TrainingGovernancePanel = ({
  courseId,
  courseTitle,
  includeAiSection = true,
}: TrainingGovernancePanelProps) => {
  const {
    data: overview,
    isLoading: isOverviewLoading,
    isError: isOverviewError,
  } = useGetTrainingAdminOverviewQuery({ courseId }, { skip: !courseId });
  const {
    data: audiencesData,
    isLoading: isAudiencesLoading,
    isError: isAudiencesError,
  } = useGetTrainingAdminAudiencesQuery();
  const {
    data: governanceData,
    isLoading: isGovernanceLoading,
    isError: isGovernanceError,
  } = useGetTrainingAdminContentGovernanceQuery({ courseId, missingOnly: true }, { skip: !courseId });

  const audiences = useMemo<TrainingAdminAudience[]>(() => audiencesData?.results ?? [], [audiencesData]);
  const governanceItems = useMemo(() => governanceData?.results ?? [], [governanceData]);

  const gapTotal = useMemo(() => {
    if (!overview) return 0;
    return (
      overview.contentWithoutAssetClass +
      overview.contentWithoutTopic +
      overview.contentWithoutOwner +
      overview.internalContentWithoutAudiencePolicy +
      overview.notebookContentWithoutLabProfile
    );
  }, [overview]);

  const isLoading = isOverviewLoading || isAudiencesLoading || isGovernanceLoading;
  const isError = isOverviewError || isAudiencesError || isGovernanceError;

  return (
    <section className={cl.block}>
      <div className={cl.blockHead}>
        <div>
          <h3>Training Governance</h3>
          <p className={cl.governanceMuted}>
            Read-only control surface for ownership, entitlement gaps and notebook readiness in {courseTitle}.
          </p>
        </div>
        <span className={cl.sectionHint}>Course ID {courseId}</span>
      </div>

      {isLoading ? <p>Loading governance data...</p> : null}
      {isError ? <p className={cl.errorText}>Failed to load training governance data.</p> : null}

      {!isLoading && !isError && overview ? (
        <>
          <section className={cl.kpiGrid}>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Course Owners</span>
              <strong>{overview.ownerAssignments}</strong>
              <span className={cl.governanceMuted}>
                {overview.ownerAssignments > 0 ? "Coverage present" : "Owner assignment missing"}
              </span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Reviewers / Instructors</span>
              <strong>
                {overview.reviewerAssignments} / {overview.instructorAssignments}
              </strong>
              <span className={cl.governanceMuted}>Course support roles</span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Content Gaps</span>
              <strong>{governanceItems.length}</strong>
              <span className={cl.governanceMuted}>{gapTotal} total governance flags</span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Notebook Readiness</span>
              <strong>
                {Math.max(overview.notebookItems - overview.notebookContentWithoutLabProfile, 0)} / {overview.notebookItems}
              </strong>
              <span className={cl.governanceMuted}>Labs with active profile</span>
            </div>
          </section>

          {overview.coursesWithoutOwner > 0 ? (
            <p className={cl.errorText}>
              This course currently has no course owner assignment. Ownership should be assigned before production rollout.
            </p>
          ) : null}

          <div className={cl.governanceSplit}>
            <section className={cl.governanceSection}>
              <div className={cl.blockHead}>
                <h3>Governance Snapshot</h3>
                <span className={cl.sectionHint}>Course-wide coverage</span>
              </div>
              <div className={cl.tableWrap}>
                <table className={cl.dataTable}>
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Courses without owner</td>
                      <td>{overview.coursesWithoutOwner}</td>
                    </tr>
                    <tr>
                      <td>Owner assignments</td>
                      <td>{overview.ownerAssignments}</td>
                    </tr>
                    <tr>
                      <td>Reviewer assignments</td>
                      <td>{overview.reviewerAssignments}</td>
                    </tr>
                    <tr>
                      <td>Instructor assignments</td>
                      <td>{overview.instructorAssignments}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section className={cl.governanceSection}>
              <div className={cl.blockHead}>
                <h3>Content Requiring Attention</h3>
                <span className={cl.sectionHint}>{governanceItems.length} flagged items</span>
              </div>
              <div className={cl.tableWrap}>
                <table className={cl.dataTable}>
                  <thead>
                    <tr>
                      <th>Content</th>
                      <th>Access</th>
                      <th>Flags</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {governanceItems.length === 0 ? (
                      <tr>
                        <td colSpan={4}>No governance gaps detected for this course.</td>
                      </tr>
                    ) : null}
                    {governanceItems.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className={cl.governanceCell}>
                            <strong>{item.name}</strong>
                            <span className={cl.governanceMuted}>
                              {contentKindLabels[item.content_kind]} / {item.status}
                            </span>
                            <span className={cl.governanceMuted}>
                              Owner: {item.owner?.email ?? "Unassigned"}
                            </span>
                          </div>
                        </td>
                        <td>
                          <div className={cl.governanceCell}>
                            <span>{accessScopeLabels[item.access_scope]}</span>
                            <span className={cl.governanceMuted}>
                              Asset classes {item.assetClassCount}, topics {item.topicCount}
                            </span>
                            {item.content_kind === "notebook" ? (
                              <span className={cl.governanceMuted}>
                                Lab: {item.labReady ? "ready" : item.hasLab ? "needs setup" : "missing"}
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <div className={cl.flagList}>
                            {item.governanceFlags.map((flag) => (
                              <span key={flag} className={cl.flagPill}>
                                {governanceFlagLabels[flag]}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td>{formatDateTime(item.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          {includeAiSection ? <TrainingAiGovernanceSection courseId={courseId} courseTitle={courseTitle} /> : null}
          <TrainingAudienceCrudSection
            audiences={audiences}
            isLoading={isAudiencesLoading}
            isError={isAudiencesError}
          />
          <TrainingCourseRoleCrudSection courseId={courseId} courseTitle={courseTitle} />
          <TrainingGrantCrudSection
            audiences={audiences}
            isLoadingAudiences={isAudiencesLoading}
            isErrorAudiences={isAudiencesError}
          />
        </>
      ) : null}
    </section>
  );
};

export default TrainingGovernancePanel;
