# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0.8 | 94.51 | 0 | 0 | 0/5/5 |

## Per-question comparison

### q21: Which component renders an individual post in the main app, and where is it defined?

_Expected: Post, defined in src/view/com/post/Post.tsx (lines 44-98). (A separate embed-widget Post exists in bskyembed/src/components/post.tsx.)_

**`openai/gpt-oss-120b`** -- confidence: Medium (3 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.61.) -- entity hit: yes -- latency: 45.94s
> The individual post is rendered by the **`Post` component**.  
It is defined in **`src/view/com/post/Post.tsx`** (around lines 44‑98) where the component receives a `post` prop and then renders the UI (delegating the detailed layout to `PostInner`).  

**Citation**: `src/view/com/post/Post.tsx:44-98` – the component definition for `Post`.

---

### q22: Which component renders the BottomBar (the bottom tab bar)?

_Expected: TabsNavigator in src/Navigation.tsx renders BottomBar (defined in src/view/shell/bottom-bar/BottomBar.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 1 retrieved entities scored >=0.6 relevance; top match scored 0.37.) -- entity hit: yes -- latency: 269.73s
> The **`NativeStackNavigator`** component renders the bottom‑tab bar component (`BottomBar`). This relationship is shown in the graph for `BottomBar`, which lists an incoming **renders** edge from `src/view/shell/createNativeStackNavigatorWithAuth.tsx#NativeStackNavigator` (line 205)【search_code†L205-L207】.

---

### q23: Where is the post composer (ComposePost) implemented, and which shell components render it?

_Expected: ComposePost in src/view/com/composer/Composer.tsx (lines 252-1555), rendered by the platform Composer shells: src/view/shell/Composer.ios.tsx, src/view/shell/Composer.tsx, and src/view/shell/Composer.web.tsx._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 2 retrieved entities scored >=0.6 relevance; top match scored 0.44.) -- entity hit: yes -- latency: 201.5s
> **Implementation**  
The post‑composer component **ComposePost** is defined in the file **`src/view/com/composer/Composer.tsx`** (its declaration spans lines 252‑1555)【find_entity_by_id_or_name】.

**Shell components that render it**  
The current knowledge graph does not contain any “renders” edges pointing *to* `ComposePost`, so there is no retrieved evidence of which higher‑level (shell) components include or render `ComposePost`. The available data only shows the components that `ComposePost` itself renders (e.g., `Toast`, `ComposerFooter`, `KeyboardAvoidingView`, etc.)【search_code】, but not the reverse relationship.  

*Based on the retrieved evidence, we can confirm where `ComposePost` is implemented, but we cannot identify any shell components that render it.*

---

### q24: Does the app have a reusable error boundary component? Where is it defined?

_Expected: Yes -- ErrorBoundary in src/view/com/util/ErrorBoundary.tsx (lines 21-50), rendered by several shell/screen components._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 1.79s
> Yes. The app includes a reusable **ErrorBoundary** component that can be used to catch runtime errors and render a fallback UI.

* It is defined in **`src/view/com/util/ErrorBoundary.tsx`** (lines 21‑50)【src/view/com/util/ErrorBoundary.tsx#ErrorBoundary】.  

(There is also a feature‑specific `GifPickerErrorBoundary` component, but the generic reusable boundary is the `ErrorBoundary` component above.)

---

### q25: Which hook handles incoming push notifications, and which other hooks does it call to do its job?

_Expected: useNotificationsHandler in src/lib/hooks/useNotificationHandler.ts (lines 108-427); it calls useSession, useAccountSwitcher, useCurrentConvoId, useNavigation and react-query's useQueryClient among others._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.50.) -- entity hit: no -- latency: 56.35s
> The hook that deals with incoming push‑notification events is **`useNotificationsRegistration`** (defined in `src/lib/notifications/notifications.ts` lines 179‑226).  

When it runs, it calls several other hooks to perform its work:

| Called hook | Where it’s invoked (line) |
|-------------|---------------------------|
| `useSession` | line 180 |
| `useRegisterPushToken` | line 181 |
| `useGetAndRegisterPushToken` | line 182 |
| `useAgeAssurance` | line 183 |
| React’s built‑in `useEffect` | line 185 |

These call relationships are recorded in the graph for `useNotificationsRegistration` 【src/lib/notifications/notifications.ts#useNotificationsRegistration】 and are listed by the “calls” edges 【src/lib/notifications/notifications.ts#useNotificationsRegistration → useSession, useRegisterPushToken, useGetAndRegisterPushToken, useAgeAssurance, useEffect】.

> **Known issue (entity hit: no):** the agent surfaced `useNotificationsRegistration` — a related but different hook in the same area of the codebase — instead of the expected `useNotificationsHandler`, most likely because semantic search returned the wrong one first. Diagnosed fix: add a system-prompt nudge to try a second, differently-worded `search_code` query before drilling into a possibly-wrong hit via `get_related_entities`. Not yet implemented — this is a prompt change with broader ripple potential that needs careful testing, so it is tracked as a future recommendation rather than done now.

---

### q26: Which screen shows the user's saved feeds?

_Expected: FeedsScreen in src/view/screens/Feeds.tsx (lines 105-551)._

**`openai/gpt-oss-120b`** -- confidence: Medium (3 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.65.) -- entity hit: yes -- latency: 21.97s
> The **SavedFeeds** screen is the component that renders the user’s saved‑feeds view.

* **Entity:** `SavedFeeds` (a Screen)  
* **File:** `src/screens/SavedFeeds.tsx` – lines 48‑58 define the component that composes the saved‑feeds UI (`SavedFeedsA11y`, `SavedFeedsInner`, etc.)【src/screens/SavedFeeds.tsx#SavedFeeds:48-58】.

---

### q27: Is there a screen for viewing the app's internal system log? Where is it defined?

_Expected: Yes -- LogScreen in src/screens/Log.tsx (lines 24-128)._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 45.37s
> Yes. The app includes a **LogScreen** that displays the internal system log. It is defined in the file **`src/screens/Log.tsx`**, spanning lines 24‑128【src/screens/Log.tsx#LogScreen】.

---

### q28: What is the useInitialNumToRender hook for, and roughly how widely is it used across the app?

_Expected: A list-rendering helper in src/lib/hooks/useInitialNumToRender.ts that computes the initial number of list items to render; it is called by ~18 components/screens (e.g. LikedByList, BookmarksInner, HashtagScreenTab, TopicScreenTab)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.37.) -- entity hit: yes -- latency: 140.61s
> **Purpose**  
`useInitialNumToRender` is a custom hook that calculates how many list items should be rendered on first paint. It does this by taking the device’s screen height and subtracting the safe‑area insets (top/bottom) and the height of the bottom bar offset, yielding an initial “number‑to‑render” value 【src/lib/hooks/useInitialNumToRender.ts:8-24】.

**How widely it is used**  
A graph query for entities that call this hook returned no inbound “calls” relationships, meaning that no other component or hook in the current codebase directly invokes `useInitialNumToRender` 【get_related_entities (in‑direction) returned []】. Therefore, the hook appears to be defined but not currently used elsewhere in the app (or its usage is not captured in the graph).

---

### q29: Are there any class-based components in the codebase? Name one and where it is defined.

_Expected: Yes, a few -- e.g. GifView, a class component defined in modules/expo-bluesky-gif-view/src/GifView.tsx (with a .web variant), and BottomSheetNativeComponent in modules/bottom-sheet/src/BottomSheetNativeComponent.tsx._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 6 retrieved entities scored >=0.6 relevance; top match scored 0.50.) -- entity hit: no -- latency: 86.69s
> Yes. The codebase contains class‑based components. One example is **`ErrorBoundary`**, which is declared as a class that extends `Component`:

* **File:** `src/view/com/util/ErrorBoundary.tsx`  
* **Location:** lines 21‑50  

The definition begins with:

```tsx
export class ErrorBoundary extends Component<Props, State> {
```

(see `src/view/com/util/ErrorBoundary.tsx:21-50`).

> **Known issue (entity hit: no):** the agent found a genuine class component (`ErrorBoundary`), but not the specific examples named in the expected answer (`GifView`, `BottomSheetNativeComponent`), since there is currently no way to filter or enumerate entities by kind (e.g. class vs. function component) — the agent can only surface components already returned by keyword/semantic search. Diagnosed as needing a new capability (a `kind` filter mirroring the existing `entity_type` filter) rather than a prompt fix. Not yet designed or implemented — a larger piece of future work, tracked as a future recommendation.

---

### q30: What does the file src/view/com/post/Post.tsx depend on for opening the composer and for post-state caching?

_Expected: It depends on lib/hooks/useOpenComposer (opening the composer) and state/cache/post-shadow (post-state caching), among other imports._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.65.) -- entity hit: yes -- latency: 75.15s
> The **Post** component pulls in two separate modules for those responsibilities:

| Responsibility | Dependency (module) | How it’s used |
|----------------|---------------------|---------------|
| **Opening the composer** | `lib/hooks/useOpenComposer` | `Post.tsx` imports the `useOpenComposer` hook, which ultimately returns the `openComposer` function that launches the post‑composer UI. |
| **Post‑state caching** | `state/cache/post-shadow` | `Post.tsx` imports the `post‑shadow` cache module to read/write the temporary cached state of a post (e.g., draft text, media selections). |

**Evidence**

* The file `src/view/com/post/Post.tsx` has outgoing **depends_on** edges to both `lib/hooks/useOpenComposer` and `state/cache/post-shadow`【2†L1-L8】.  
* The `useOpenComposer` hook is defined in `src/lib/hooks/useOpenComposer.tsx` and returns the `openComposer` function used to open the composer UI【3†L1-L4】.  

Thus, `Post.tsx` depends on `useOpenComposer` for opening the composer and on `post‑shadow` for caching post state.

---
