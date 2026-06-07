# Course Structure Reset And Import

This project now supports a strict Coursera-like tree:

- `Course`
- `Module` (`module` or `final_assessment`)
- `Lesson`
- `Section` (`introduction`, `main`, `conclusion`)
- `ContentItem` (`activityType`: `video`, `text`, `quiz`, `assignment`)

## 1) Reset and seed two programming demo courses

Run on backend environment:

```bash
python manage.py reset_online_courses_coursera_demo --confirm-reset RESET
```

What it does:

- removes all existing `OnlineCourse` rows (unless `--skip-purge` is passed);
- seeds **2 programming courses**;
- each course has:
  - 3 regular modules;
  - 2 lessons per module;
  - each lesson has video + briefing PDF + reading(text) + quiz + assignment(notebook);
  - a final `Final Project / Exam` module with a capstone notebook;
- creates cohorts + sessions;
- re-links workspace course cards to newly seeded courses;
- optionally enrolls demo student (`mailpit.student@example.com`) if account exists.

Optional flags:

```bash
python manage.py reset_online_courses_coursera_demo --skip-purge --teacher-email teacher@learning-hub.local --student-email mailpit.student@example.com
```

Safety:

- purge is blocked unless `--confirm-reset RESET` is provided;
- use `--skip-purge` to append/update demo seeds without deleting all courses.

## 2) Import course from Coursera-like JSON

API endpoint:

- `POST /online/admin/course-builder/import/`

Expected payload:

```json
{
  "source": "coursera_json",
  "payload": {
    "title": "Imported course",
    "modules": [
      {
        "title": "Module 1 (Week 1)",
        "lessons": [
          {
            "title": "Lesson 1",
            "contentItems": [
              { "type": "video", "title": "Video", "url": "https://..." },
              { "type": "reading", "title": "Reading", "text": "..." },
              { "type": "quiz", "title": "Quiz", "questions": [{ "question": "..." }] },
              { "type": "assignment", "title": "Assignment", "trainingContentId": 123 }
            ]
          }
        ]
      }
    ],
    "finalAssessment": {
      "title": "Final Project / Exam",
      "description": "Final summary",
      "instructions": "Submit the final deliverable"
    }
  }
}
```

Notes:

- `payload.course.modules` is also accepted;
- if `modules` are absent, importer can fallback to `lessons` and create a default module;
- `trainingContentId` for assignment items is resolved to `TrainingContentItem` and linked safely.
- canonical content item types:
  - `video` -> `activityType=video`
  - `reading`/`text` -> `activityType=text`
  - `quiz` -> `activityType=quiz`
  - `assignment` -> `activityType=assignment`
