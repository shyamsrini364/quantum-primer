# Frontend handoff

Build a beginner-friendly Quantum Primer chat experience over this Python API. The backend is implemented; the web frontend is a separate next step.

## Views and behavior

1. Welcome: explain that answers come from the user's selected books. Show grouped question chips from `GET /sample-questions`.
2. Chat: submit a question (3–2,000 characters). Disable submit while waiting. Show the response exactly with its numbered citations. Render Markdown safely with raw HTML disabled.
3. Sources panel: each citation shows title, author and page/section. Clicking `[1]` focuses its source card. Do not invent external links or book excerpts.
4. No-answer state: display `insufficient_context` and suggest adding a relevant source or asking a narrower question.
5. Service unavailable: distinguish 503 from lack of source coverage. Offer retry.
6. Demo banner: show “Demo fixture — no books or live model connected” whenever `mode=demo`.

## Server-side integration

The browser calls your app's own `/api/chat`. That server route validates the request and forwards it to the Python `/chat` with `X-API-Key` from a server-only environment variable. Never expose provider keys or the backend key using public environment variables. Add authentication and request quotas before public deployment. CORS is not authentication.

Python request: `{"question":"What does the author mean by EZ water?"}`.
Response: `answer`, `status`, `mode`, and `citations[]` with `id`, `source_id`, `title`, `author`, `locator`.

Messages may be displayed as a chat transcript, but each request is currently independent. Do not imply the backend remembers prior messages. No streaming, document uploads, user accounts, multi-tenancy or citations-to-PDF navigation is implemented.

## Suggested design brief

Make it curious, approachable and easy to read. Prioritize clear explanations and visible sources over scientific decoration. Sample questions should help someone who has never studied quantum biology begin exploring.
