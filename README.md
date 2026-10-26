# CCSE Conference Platform — Frontend Prototype

**Frontend / UX Lead:** Jonathan Cruz  
**Milestone:** Milestone 1

This repository contains a frontend prototype for the CCSE Conference Intelligence and Planning Platform. It demonstrates how an authorized reviewer could inspect AI-extracted conference information before approving it for a yearly conference edition.

## Features

- Review conference name, year, start and end dates, location, and attendance format.
- View a suggested deadline and edit its type and date.
- Display source links, supporting text, and warnings for missing information.
- Edit suggested values and approve or reject the sample suggestion.
- Show the approved edition after approval.
- Reset the sample to repeat the demonstration.
- Adapt the layout to smaller screens.

## Open the prototype

Download `index.html` and open it in a web browser. No installation or server is required.

If GitHub Pages is enabled for this repository, open:

https://printsbycruz.github.io/frontend/

## Demonstration

1. Review the fictional conference and its suggested values.
2. Read the warnings and supporting text.
3. Enter a location or correct another suggested value.
4. Click **Approve edited values** to display the approved edition.
5. Click **Reset demo**, then try **Reject suggestion**.

## Current limitations

This is a frontend demonstration, not the integrated application. Conference details and supporting text are fictional, and source links use example.org placeholders. Decisions are stored in this browser using local storage, when available. They are not saved to the team's database or shared with other users.

The prototype does not yet include live AI extraction, backend API integration, authentication, role enforcement, or deadline notifications. Browser approval demonstrates the interaction only; production approval must be validated and saved by the backend.

## Tools and integration plan

This standalone prototype uses HTML, CSS, and JavaScript. The team's proposed application stack is Django, PostgreSQL, and Django templates with Bootstrap. The next step is to integrate the review interface with the extraction response and backend approval workflow, keeping pending suggestions separate from approved conference editions.

## Files

- `index.html` — self-contained review-screen prototype.
- `README.md` — setup, demonstration, and integration notes.


## AI extraction and automation contribution

The Gemini AI component is implemented in the Django conferences app. It supports bounded official-page
research, structured extraction, source evidence, conflict review, candidate APIs, batch refreshes, and
unchanged-source detection. It never automatically approves data.

See [AI handoff and setup](docs/AI_HANDOFF.md), [API contract](docs/AI_API.md), and
[validation results](VALIDATION.md). The contribution has 89 passing tests and live examples for
Computing Frontiers and DjangoCon US. The frontend prototype above remains a separate integration task.

Install Python 3.12 dependencies from requirements-ai.lock.txt and create a private .env from .env.example.
The school-maintenance and backend-approval checklists are in docs/. Do not upload the private .env or local databases.
