Build a portal called SpecForge AI.

Goal:
Business users should upload messy requirements documents and the system should generate structured Functional Specifications, Technical Specifications, User Stories, Acceptance Criteria, Open Questions, and Review Comments.

Tech stack:
- Frontend: Next.js + React + Tailwind
- Backend: FastAPI
- Database: Postgres
- File storage: local filesystem for now, but design so it can later move to Azure Blob
- LLM layer: create an abstraction so Gemini, Claude, or Azure OpenAI can be swapped later
- Initial LLM provider: Gemini API
- Document parsing: support PDF, DOCX, TXT initially

Core UX:
1. Dashboard showing projects
2. Create new project
3. Upload requirement documents
4. Show extracted requirement summary
5. Show missing questions / gaps
6. Generate Functional Spec
7. Generate Technical Spec
8. Generate Jira-style user stories
9. Allow editing generated output
10. Export as Markdown and DOCX

Important architecture:
Implement a reusable “Skill Engine”.

A skill is:
- system instruction
- prompt template
- output schema
- examples
- parser

Create these skills:
1. requirement_extractor
2. gap_detector
3. functional_spec_generator
4. technical_spec_generator
5. user_story_generator
6. reviewer

Folder structure:
backend/
  app/
    main.py
    api/
      projects.py
      documents.py
      specs.py
    services/
      llm/
        base.py
        gemini_provider.py
      skills/
        skill_engine.py
        requirement_extractor/
          instruction.md
          template.md
          schema.json
        functional_spec/
          instruction.md
          template.md
          schema.json
        technical_spec/
          instruction.md
          template.md
          schema.json
        user_stories/
          instruction.md
          template.md
          schema.json
        reviewer/
          instruction.md
          template.md
          schema.json
      documents/
        parser.py
      export/
        markdown_exporter.py
        docx_exporter.py
    models/
      project.py
      document.py
      spec.py
    db.py

frontend/
  app/
    page.tsx
    projects/
    components/
      ProjectCard.tsx
      UploadPanel.tsx
      SpecEditor.tsx
      GapQuestions.tsx
      OutputTabs.tsx

Data model:
- Project
- Document
- ExtractedRequirement
- SpecVersion
- GapQuestion
- ReviewComment

Spec generation workflow:
1. User creates project
2. User uploads documents
3. Backend parses documents into text
4. requirement_extractor skill creates structured requirement JSON
5. gap_detector skill finds missing information
6. functional_spec_generator creates functional spec
7. technical_spec_generator creates technical spec
8. user_story_generator creates Jira-ready stories
9. reviewer checks completeness, ambiguity, security, data, and implementation risks
10. User can edit and export

Important product requirements:
- Do not make this a generic chatbot
- Make it a guided workflow
- Each generated section should show confidence and source reference where possible
- Unclear information should go into Open Questions, not hallucinated
- Generated specs must be versioned
- UI should look premium, clean, enterprise-grade, and suitable for business users
- Use tabs for Functional Spec, Technical Spec, User Stories, Review Comments, Open Questions
- Include a left project/document panel, center spec editor, and right review/gaps panel

Initial implementation:
Build a working MVP with mocked LLM responses first if API key is missing.
Then wire Gemini provider using environment variable GEMINI_API_KEY.

Environment:
- Use .env
- Never expose API key in frontend
- Add README with setup steps

Deliverables:
1. Working backend
2. Working frontend
3. Skill engine implementation
4. Sample skill prompts
5. Sample project flow
6. README