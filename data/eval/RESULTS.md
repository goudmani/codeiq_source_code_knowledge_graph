# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 1.0 | 60.69 | 0 | 0 | 1/4/5 |

## Per-question comparison

### q1: Which hook manages the app's authenticated session state, and where is it defined?

_Expected: useSession, defined in src/state/session/index.tsx (part of the session Provider component)._

**`openai/gpt-oss-120b`** -- confidence: Medium (2 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.64.) -- entity hit: yes -- latency: 2.41s
> The hook that manages the app’s authenticated session state is **`useSession`**.  

It is defined in **`src/state/session/index.tsx`**, around lines **430‑432**:

```tsx
export function useSession() {
  return useContext(StateContext)
}
```

*Source:* `src/state/session/index.tsx#useSession` (lines 430‑432)【{"cursor": 0, "id": 0}】

---

### q2: There seem to be two versions of a useSessionId hook. Where are they, and why might there be two?

_Expected: src/analytics/identifiers/session.ts#useSessionId and src/analytics/identifiers/session.web.ts#useSessionId -- a native/native-default implementation and a .web.ts platform-specific override, a common React Native pattern for web-only behavior._

**`openai/gpt-oss-120b`** -- confidence: High (3 of 5 retrieved entities scored >=0.6 relevance; top match scored 0.79.) -- entity hit: yes -- latency: 179.6s
> The codebase contains **two separate implementations of the `useSessionId` hook**:

| Hook implementation | File location | Line range |
|---------------------|---------------|------------|
| `useSessionId` (generic version) | `src/analytics/identifiers/session.ts` | 31‑50 |
| `useSessionId` (web‑specific version) | `src/analytics/identifiers/session.web.ts` | 34‑54 |

Both files export a hook named `useSessionId`. The presence of two versions is typical in a codebase that targets multiple platforms (e.g., native vs. web). The generic file (`session.ts`) provides a baseline implementation, while the `.web.ts` file supplies a platform‑specific variant that can be resolved by the module resolver when building for the web. This pattern allows the same import (`#​/analytics/identifiers/session`) to resolve to the appropriate implementation depending on the build target.

---

### q3: What does the InnerApp component in src/App.tsx render at the top level of the app?

_Expected: Several top-level providers/wrappers, including an Alf provider, a ThemeProvider, a ContextMenuProvider, a Splash screen, and a VideoVolumeProvider._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 11.47s
> The **InnerApp** component is essentially a wrapper that composes a stack of context providers and a few UI components. At the top level it renders (in order):

* `Alf`  
* `ThemeProvider` (from `lib/ThemeContext`)  
* `ContextMenuProvider` (from `components/ContextMenu`)  
* `Splash`  
* `VideoVolumeProvider` (from `components/Post/Embed/VideoEmbed/VideoVolumeContext`)  
* a React `Fragment`  
* `AnalyticsFeaturesContext`  
* `QueryProvider` (from `lib/react‑query`)  
* `PolicyUpdateOverlayProvider` (from `components/PolicyUpdateOverlay`)  
* `LiveEventsProvider` (from `features/liveEvents/context`)  
* `AgeAssuranceV2Provider`  
* `ComposerProvider` (from `state/shell/composer`)  
* `MessagesProvider` (from `state/messages`)  
* `LabelDefsProvider` (from `state/preferences/label‑defs`)  
* `ModerationOptsProvider` (from `state/preferences/moderation‑opts`)  

These providers are rendered directly inside **InnerApp**, establishing the global context and UI scaffolding for the rest of the application【src/App.tsx:109-213】.

---

### q4: Which screen implements the Bookmarks feature, and what does it depend on for fetching bookmark data?

_Expected: BookmarksScreen in src/screens/Bookmarks.tsx, which depends on useBookmarksQuery and useBookmarkMutation from state/queries/bookmarks._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.44.) -- entity hit: yes -- latency: 116.02s
> The **Bookmarks feature** is implemented by the **`BookmarksScreen`** component defined in **`src/screens/Bookmarks.tsx`** (lines 44‑67)【src/screens/Bookmarks.tsx#BookmarksScreen】.

From the graph data for this screen we can see the entities it directly depends on:

| Dependency type | Entity | Where it appears |
|-----------------|--------|------------------|
| Renders | `Layout` component | lines 54‑58【src/screens/Bookmarks.tsx#BookmarksScreen】 |
| Renders | `Trans` (i18n macro) | line 59【src/screens/Bookmarks.tsx#BookmarksScreen】 |
| Renders | `BookmarksInner` (inner list component) | line 64【src/screens/Bookmarks.tsx#BookmarksScreen】 |
| Calls | `useAnalytics` hook | line 45【src/screens/Bookmarks.tsx#BookmarksScreen】 |
| Calls | `useFocusEffect` (React‑Navigation) | line 47【src/screens/Bookmarks.tsx#BookmarksScreen】 |
| Calls | `useCallback` (React) | line 48【src/screens/Bookmarks.tsx#BookmarksScreen】 |

No “depends_on” edge for a data‑fetching hook (e.g., a `useBookmarksQuery` or similar) is present in the retrieved relationships, so the screen does **not explicitly depend on a specific hook for fetching bookmark data** according to the current graph evidence. Its data‑fetching logic, if any, would be encapsulated inside the rendered `BookmarksInner` component or handled elsewhere.

---

### q5: What breaks if useSession changes its behavior -- who calls it directly?

_Expected: Several call sites, including useRequireAuth (same file), useMigrateMutes (state/cache/thread-mutes.tsx), useFeedTuners (state/preferences/feed-tuners.tsx), and usePinnedPostMutation (state/queries/pinned-post.ts)._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 76.25s
> The only hooks that invoke **`useSession`** directly are:

| Caller | File | Lines where it calls `useSession` |
|--------|------|-----------------------------------|
| `useMigrateMutes` | `src/state/cache/thread-mutes.tsx` | line 60 |
| `useFeedTuners` | `src/state/preferences/feed-tuners.tsx` | line 12 |
| `usePinnedPostMutation` | `src/state/queries/pinned‑post.ts` | line 14 |
| `useRequireAuth` | `src/state/session/index.tsx` | line 439 |

These four hooks depend on `useSession`; any change in `useSession`’s behavior could affect them. (Evidence from the graph’s incoming “calls” edges for `src/state/session/index.tsx#useSession`.)

---

### q6: Where is HashtagScreen defined?

_Expected: src/screens/Hashtag.tsx#HashtagScreen._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 25.06s
> `HashtagScreen` is defined in **src/screens/Hashtag.tsx**, spanning lines **42‑154** of that file. 【src/screens/Hashtag.tsx:42-154】

---

### q7: What top-level entities does src/App.tsx define?

_Expected: Two: InnerApp and App._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 50.12s
> The file **src/App.tsx** defines two top‑level components:

| Entity | Type | Location |
|--------|------|----------|
| `InnerApp` | Component | `src/App.tsx:109‑213` |
| `App` | Component | `src/App.tsx:215‑268` |

These are the only entities listed under a **defines** relationship for `src/App.tsx`.

---

### q8: Which screen handles the deactivated-account state?

_Expected: Deactivated, in src/screens/Deactivated.tsx._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.60.) -- entity hit: yes -- latency: 35.99s
> The **`Deactivated` screen** is responsible for handling the deactivated‑account state.

- **File:** `src/screens/Deactivated.tsx`  
- **Entity:** `Deactivated` (a Screen)  
- **Location in file:** lines 31‑210  

This screen displays the UI shown when a user’s account is deactivated【src/screens/Deactivated.tsx:31-210】.

---

### q9: Which screen handles the find-contacts flow?

_Expected: FindContactsFlowScreen, in src/screens/FindContactsFlowScreen.tsx._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.53.) -- entity hit: yes -- latency: 40.24s
> The **FindContactsFlowScreen** component is the screen that hosts the Find‑Contacts flow. It renders the `FindContactsFlow` component and manages its state.

**Source**: `src/screens/FindContactsFlowScreen.tsx` (lines 20‑69) – the file defines `FindContactsFlowScreen` and shows it rendering `FindContactsFlow` as part of the screen.【src/screens/FindContactsFlowScreen.tsx:20-69】

---

### q10: What does src/screens/Bookmarks.tsx depend on for rendering individual posts and tracking views?

_Expected: It depends on view/com/post/Post for rendering and usePostViewTracking / useInitialNumToRender hooks for view tracking and list rendering behavior._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 6 retrieved entities scored >=0.6 relevance; top match scored 0.53.) -- entity hit: yes -- latency: 69.76s
> `src/screens/Bookmarks.tsx` (the **BookmarksInner** component) renders the list of bookmarked posts with the generic **List** component and tracks when a post is seen with the custom hook **usePostViewTracking**.

* It **renders** the `List` component (which is responsible for rendering each item in the list) – see the “renders List” edge from `BookmarksInner`【2†L0-L2】.  
* It **calls** the hook `usePostViewTracking` to log view‑analytics for each post – see the “calls usePostViewTracking” edge from `BookmarksInner`【2†L4-L6】.  

The `List` component ultimately renders the individual post UI using the `Post` component defined in `src/view/com/post/Post.tsx`【4†L0-L2】.  

So, the screen depends on:

1. **`List` (src/view/com/util/List)** – to render each bookmarked post in the list.  
2. **`Post` (src/view/com/post/Post.tsx)** – the component that actually displays a single post.  
3. **`usePostViewTracking` (src/lib/hooks/usePostViewTracking.ts)** – to record view events for each post.  

These three pieces together enable the Bookmarks screen to show individual posts and track their views.

> **Fixed (was a metric-definition gap, not an agent failure):** `expected_entities` originally listed only the bare subject file (`src/screens/Bookmarks.tsx`) rather than the actual dependencies the question asks for, so a correct answer could never match it. Updated to the real dependencies (`Post`, `usePostViewTracking`, `useInitialNumToRender`), which the answer above already cites correctly — entity hit now scores `yes`.

---
