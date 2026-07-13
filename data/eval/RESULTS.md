# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0.8 | 74.08 | 1 | 0 | 1/5/3 |

## Per-question comparison

### q1: Which hook manages the app's authenticated session state, and where is it defined?

_Expected: useSession, defined in src/state/session/index.tsx (part of the session Provider component)._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 8 retrieved entities scored >=0.6 relevance; top match scored 0.59.) -- entity hit: yes -- latency: 47.51s
> The hook that holds the app’s authenticated‑session state is **`useSession`**. It simply returns the session context that is provided by the `<SessionProvider>` component.

**Definition**  
- File: `src/state/session/index.tsx`  
- Lines: 430‑432  

```tsx
export function useSession() {
  return useContext(StateContext)
}
```  

(Reference: `src/state/session/index.tsx#useSession`, lines 430‑432)

---

### q2: There seem to be two versions of a useSessionId hook. Where are they, and why might there be two?

_Expected: src/analytics/identifiers/session.ts#useSessionId and src/analytics/identifiers/session.web.ts#useSessionId -- a native/native-default implementation and a .web.ts platform-specific override, a common React Native pattern for web-only behavior._

**`openai/gpt-oss-120b`** -- confidence: High (3 of 7 retrieved entities scored >=0.6 relevance; top match scored 0.79.) -- entity hit: yes -- latency: 99.55s
> The hook **`useSessionId`** is defined in two separate files:

| Hook | File (path) | Location in file |
|------|-------------|------------------|
| `useSessionId` (default) | `src/analytics/identifiers/session.ts` | lines 31‑50【0†L0-L2】 |
| `useSessionId` (web‑specific) | `src/analytics/identifiers/session.web.ts` | lines 34‑54【0†L0-L2】 |

Both files export a hook with the same name and very similar implementation (they both create a stateful `id` and subscribe to app‑state changes). The presence of a **`.web.ts`** version indicates a platform‑specific implementation: React Native projects often provide separate modules for native and web builds, and the build system will pick `session.web.ts` when bundling for the web, while `session.ts` is used for the other platforms (iOS/Android). This allows the hook to handle platform‑specific APIs or behaviours while keeping a common public API.

---

### q3: What does the InnerApp component in src/App.tsx render at the top level of the app?

_Expected: Several top-level providers/wrappers, including an Alf provider, a ThemeProvider, a ContextMenuProvider, a Splash screen, and a VideoVolumeProvider._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 7 retrieved entities scored >=0.6 relevance; top match scored 0.61.) -- entity hit: yes -- latency: 110.54s
> The **InnerApp** component (defined in `src/App.tsx`) renders a top‑level **React Fragment** that wraps a series of context‑ and UI‑providers for the whole application. According to the graph of its `renders` edges, the fragment contains:

* `Alf`  
* `ThemeProvider` (from `lib/ThemeContext`)  
* `ContextMenuProvider` (from `components/ContextMenu`)  
* `Splash`  
* `VideoVolumeProvider` (from `components/Post/Embed/VideoEmbed/VideoEmbed`)  
* `AnalyticsFeaturesContext`  
* `QueryProvider` (from `lib/react‑query`)  
* `PolicyUpdateOverlayProvider` (from `components/PolicyUpdateOverlay`)  
* `LiveEventsProvider` (from `features/liveEvents/context`)  
* `AgeAssuranceV2Provider` (from `ageAssurance`)  
* `ComposerProvider` (from `state/shell/composer`)  
* `MessagesProvider` (from `state/messages`)  
* `LabelDefsProvider` (from `state/preferences/label‑defs`)  
* `ModerationOptsProvider` (from `state/preferences/moderation‑opts`)  

All of these are rendered inside a single `Fragment` (external) — the top‑level structure of the app 【get_related_entities result】.

---

### q4: Which screen implements the Bookmarks feature, and what does it depend on for fetching bookmark data?

_Expected: BookmarksScreen in src/screens/Bookmarks.tsx, which depends on useBookmarksQuery and useBookmarkMutation from state/queries/bookmarks._

**`openai/gpt-oss-120b`** -- confidence: Medium (3 of 6 retrieved entities scored >=0.6 relevance; top match scored 0.65.) -- entity hit: yes -- latency: 84.09s
> **Screen:** The Bookmarks feature is implemented by **`BookmarksScreen`** in `src/screens/Bookmarks.tsx`【0†src/screens/Bookmarks.tsx#BookmarksScreen】. This screen renders the inner component `BookmarksInner`.

**Data‑fetching dependency:** `BookmarksInner` fetches the bookmarked posts by calling the hook **`useBookmarksQuery`** (defined in `src/state/queries/bookmarks/useBookmarksQuery.ts`)【1†src/screens/Bookmarks.tsx#BookmarksInner】【2†src/state/queries/bookmarks/useBookmarksQuery.ts#useBookmarksQuery】. This hook uses the app’s agent and an infinite query to retrieve the bookmark data.

---

### q5: What breaks if useSession changes its behavior -- who calls it directly?

_Expected: Several call sites, including useRequireAuth (same file), useMigrateMutes (state/cache/thread-mutes.tsx), useFeedTuners (state/preferences/feed-tuners.tsx), and usePinnedPostMutation (state/queries/pinned-post.ts)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 4 retrieved entities scored >=0.6 relevance; top match scored 0.38.) -- entity hit: yes -- latency: 74.06s
> `useSession` is called directly by four other hooks in the codebase:

| Direct caller | File / line range |
|---------------|-------------------|
| `useMigrateMutes` – a hook that migrates thread‑mute data | `src/state/cache/thread-mutes.tsx#useMigrateMutes` (lines 58‑104)【3†L1-L4】 |
| `useFeedTuners` – a hook that manages feed‑tuning preferences | `src/state/preferences/feed-tuners.tsx#useFeedTuners` (lines 9‑52)【3†L2-L4】 |
| `usePinnedPostMutation` – a hook that provides a mutation for pinning posts | `src/state/queries/pinned‑post.ts#usePinnedPostMutation` (lines 12‑87)【3†L3-L4】 |
| `useRequireAuth` – a hook that enforces authentication before rendering | `src/state/session/index.tsx#useRequireAuth` (lines 438‑454)【3†L4-L5】 |

If the behavior of `useSession` were changed, any of these four hooks would be affected because they invoke `useSession` directly.

---

### q6: Where is HashtagScreen defined?

_Expected: src/screens/Hashtag.tsx#HashtagScreen._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 27.66s
> `HashtagScreen` is defined in **src/screens/Hashtag.tsx**, spanning lines 42‑154.  

File and location: `src/screens/Hashtag.tsx#HashtagScreen` (lines 42‑154).

---

### q7: What top-level entities does src/App.tsx define?

_Expected: Two: InnerApp and App._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 4 retrieved entities scored >=0.6 relevance; top match scored 0.59.) -- entity hit: yes -- latency: 63.75s
> `src/App.tsx` defines two top‑level components:

* **InnerApp** – a component defined from line 109 to 213 in the file【src/App.tsx#InnerApp:109-213】  
* **App** – the main component defined from line 215 to 268 in the file【src/App.tsx#App:215-268】

These are the only top‑level entities that the file declares.

---

### q8: Which screen handles the deactivated-account state?

_Expected: Deactivated, in src/screens/Deactivated.tsx._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 7 retrieved entities scored >=0.6 relevance; top match scored 0.56.) -- entity hit: yes -- latency: 89.58s
> The **`Deactivated`** screen (implemented in `src/screens/Deactivated.tsx`) is the component that handles the deactivated‑account state【src/screens/Deactivated.tsx#Deactivated:31-210】.

---

### q9: Which screen handles the find-contacts flow?

_Expected: FindContactsFlowScreen, in src/screens/FindContactsFlowScreen.tsx._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 7 retrieved entities scored >=0.6 relevance; top match scored 0.50.) -- entity hit: no -- latency: 69.94s
> The **FindContactsSettingsScreen** implements the find‑contacts flow. It is defined in `src/screens/Settings/FindContactsSettings.tsx` (lines 59‑112) and renders the onboarding intro, sync status, and related UI for the find‑contacts feature【src/screens/Settings/FindContactsSettings.tsx#FindContactsSettingsScreen】.

---

### q10: What does src/screens/Bookmarks.tsx depend on for rendering individual posts and tracking views?

_Expected: It depends on view/com/post/Post for rendering and usePostViewTracking / useInitialNumToRender hooks for view tracking and list rendering behavior._

**`openai/gpt-oss-120b`** -- confidence: None (None) -- entity hit: no -- latency: Nones
> ERROR: Error code: 400 - {'error': {'message': 'Tool choice is none, but model called a tool', 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "search_code", "arguments": {"entity_type": "Screen", "n_results": 5, "path": "src/screens/Bookmarks.tsx", "query": "function BookmarkItem"}}'}}

---
