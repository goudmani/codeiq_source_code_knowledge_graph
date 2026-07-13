# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0.8 | 66.04 | 0 | 0 | 0/5/5 |

## Per-question comparison

### q21: Which component renders an individual post in the main app, and where is it defined?

_Expected: Post, defined in src/view/com/post/Post.tsx (lines 44-98). (A separate embed-widget Post exists in bskyembed/src/components/post.tsx.)_

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 4 retrieved entities scored >=0.6 relevance; top match scored 0.57.) -- entity hit: yes -- latency: 21.53s
> The component that renders an individual post in the main app is **`Post`**. It is defined in the file **`src/view/com/post/Post.tsx`** (lines 44‑98)【bskyembed/src/components/post.tsx#Post】【src/view/com/post/Post.tsx#Post】. The `Post` component internally renders the `PostInner` component, which contains the detailed UI for a single post【src/view/com/post/Post.tsx#PostInner】.

---

### q22: Which component renders the BottomBar (the bottom tab bar)?

_Expected: TabsNavigator in src/Navigation.tsx renders BottomBar (defined in src/view/shell/bottom-bar/BottomBar.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.47.) -- entity hit: yes -- latency: 99.02s
> Based on the retrieved evidence, the codebase contains a `BottomBar` component defined in `src/view/shell/bottom-bar/BottomBar.tsx` (lines 63‑374). However, the available relationship data does not show any other component that renders this `BottomBar`. Consequently, the specific component that renders the bottom tab bar cannot be identified from the evidence that has been retrieved.

---

### q23: Where is the post composer (ComposePost) implemented, and which shell components render it?

_Expected: ComposePost in src/view/com/composer/Composer.tsx (lines 252-1555), rendered by the platform Composer shells: src/view/shell/Composer.ios.tsx, src/view/shell/Composer.tsx, and src/view/shell/Composer.web.tsx._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 2 retrieved entities scored >=0.6 relevance; top match scored 0.39.) -- entity hit: yes -- latency: 84.11s
> The model exhausted its tool-call budget before producing a final synthesis. The cited sources below were still retrieved and are valid evidence for this question.

---

### q24: Does the app have a reusable error boundary component? Where is it defined?

_Expected: Yes -- ErrorBoundary in src/view/com/util/ErrorBoundary.tsx (lines 21-50), rendered by several shell/screen components._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 27.16s
> Yes. The app includes a reusable **ErrorBoundary** component that can be used to catch rendering errors in any part of the UI.

* **Definition** – `src/view/com/util/ErrorBoundary.tsx` (component `ErrorBoundary`, lines 21‑50)【src/view/com/util/ErrorBoundary.tsx#ErrorBoundary】.  

This component is a generic error‑boundary wrapper that can be imported and used throughout the application. (A feature‑specific wrapper, `GifPickerErrorBoundary`, is also defined in `src/features/gifPicker/components/GifPickerErrorBoundary.tsx`, but the reusable core is the one above.)

---

### q25: Which hook handles incoming push notifications, and which other hooks does it call to do its job?

_Expected: useNotificationsHandler in src/lib/hooks/useNotificationHandler.ts (lines 108-427); it calls useSession, useAccountSwitcher, useCurrentConvoId, useNavigation and react-query's useQueryClient among others._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 9 retrieved entities scored >=0.6 relevance; top match scored 0.53.) -- entity hit: no -- latency: 75.85s
> The hook that is responsible for handling incoming push‑notifications is **`useNotificationsRegistration`** (defined in `src/lib/notifications/notifications.ts`).  

When it runs, it composes several other hooks to perform the registration work:

* **`useSession`** – to obtain the current account context.  
* **`useRegisterPushToken`** – the low‑level hook that actually registers a device token with the server.  
* **`useGetAndRegisterPushToken`** – a helper that first obtains a token (and performs age‑assurance checks) and then calls `useRegisterPushToken`.  
* **`useAgeAssurance`** – used inside `useGetAndRegisterPushToken` to ensure the user meets the required age.  
* **React’s `useEffect`** – to trigger the registration side‑effect when the component mounts.

These relationships are shown in the code graph for `useNotificationsRegistration`:

* `useNotificationsRegistration` **Calls**: `useSession`, `useRegisterPushToken`, `useGetAndRegisterPushToken`, `useAgeAssurance`, `useEffect`【src/lib/notifications/notifications.ts#useNotificationsRegistration】.  

* `useGetAndRegisterPushToken` **Calls**: `useAgeAssurance`, `useRegisterPushToken`, `useCallback` (external)【src/lib/notifications/notifications.ts#useGetAndRegisterPushToken】.  

Thus, `useNotificationsRegistration` is the entry point for incoming push‑notification handling, and it delegates its work to the hooks listed above.

---

### q26: Which screen shows the user's saved feeds?

_Expected: FeedsScreen in src/view/screens/Feeds.tsx (lines 105-551)._

**`openai/gpt-oss-120b`** -- confidence: Medium (2 of 6 retrieved entities scored >=0.6 relevance; top match scored 0.67.) -- entity hit: yes -- latency: 77.74s
> The **SavedFeeds** screen is responsible for displaying the user’s saved feeds.

- Defined in `src/screens/SavedFeeds.tsx` as the `SavedFeeds` component, which renders the saved‑feed UI and calls hooks such as `usePreferencesQuery` and `useA11y` to load the user’s saved feed data【src/screens/SavedFeeds.tsx:48-58】.

---

### q27: Is there a screen for viewing the app's internal system log? Where is it defined?

_Expected: Yes -- LogScreen in src/screens/Log.tsx (lines 24-128)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 5 retrieved entities scored >=0.6 relevance; top match scored 0.41.) -- entity hit: yes -- latency: 40.26s
> Yes. The app includes a **LogScreen** that displays the internal system log.

* **Definition** – `src/screens/Log.tsx` (entity `LogScreen`), lines 24‑128.  
  ```tsx
  export function LogScreen({}: NativeStackScreenProps<
    CommonNavigatorParams,
    'Log'
  >) {
    …
  }
  ```  
  (see `src/screens/Log.tsx#LogScreen`【0†src/screens/Log.tsx:24-128】)

Thus the screen for viewing the app’s internal log is defined in `src/screens/Log.tsx` as `LogScreen`.

---

### q28: What is the useInitialNumToRender hook for, and roughly how widely is it used across the app?

_Expected: A list-rendering helper in src/lib/hooks/useInitialNumToRender.ts that computes the initial number of list items to render; it is called by ~18 components/screens (e.g. LikedByList, BookmarksInner, HashtagScreenTab, TopicScreenTab)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 2 retrieved entities scored >=0.6 relevance; top match scored 0.30.) -- entity hit: yes -- latency: 70.1s
> The **`useInitialNumToRender`** hook is a utility that calculates how many list items should be rendered initially, based on the height of a single item and the available screen height (optionally adjusted by a safe‑area inset or a bottom‑bar offset). It takes optional parameters `minItemHeight` (defaulting to a constant `MIN_POST_HEIGHT`) and `screenHeightOffset`, and internally uses `useWindowDimensions`, `useSafeAreaInsets`, and a custom `useBottomBarOffset` hook to determine the effective viewport size【src/lib/hooks/useInitialNumToRender.ts:8-24】.

When we query the code graph for entities that **call** this hook, no inbound relationships are returned, indicating that the hook is not referenced elsewhere in the current codebase (or at least not captured in the graph). Therefore, its usage is minimal—essentially limited to its own definition and not widely employed across the app.

---

### q29: Are there any class-based components in the codebase? Name one and where it is defined.

_Expected: Yes, a few -- e.g. GifView, a class component defined in modules/expo-bluesky-gif-view/src/GifView.tsx (with a .web variant), and BottomSheetNativeComponent in modules/bottom-sheet/src/BottomSheetNativeComponent.tsx._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 9 retrieved entities scored >=0.6 relevance; top match scored 0.54.) -- entity hit: no -- latency: 64.82s
> The codebase does not contain any class‑based React components. All of the component definitions that were found (e.g., `Provider` in `src/components/Tooltip/index.web.tsx`, `Provider` in `src/state/shell/landing.tsx`, `Outer` in `src/components/Toast/index.tsx`, `Admonition` in `src/components/Admonition.tsx`, etc.) are written as function components using the `function` keyword or arrow functions. No component definition using `class … extends React.Component` appears in the retrieved search results. Therefore, there are no class‑based components to name.

---

### q30: What does the file src/view/com/post/Post.tsx depend on for opening the composer and for post-state caching?

_Expected: It depends on lib/hooks/useOpenComposer (opening the composer) and state/cache/post-shadow (post-state caching), among other imports._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 8 retrieved entities scored >=0.6 relevance; top match scored 0.67.) -- entity hit: yes -- latency: 99.81s
> The **Post** component (`src/view/com/post/Post.tsx`) opens the composer by using the **`useOpenComposer`** hook, and it caches post state by depending on the **post‑shadow cache** module.

* **Opening the composer** – The file lists a dependency on `lib/hooks/useOpenComposer` (`src/lib/hooks/useOpenComposer.tsx`), which provides the `useOpenComposer` hook used by the post component to trigger the composer UI. 【get_related_entities†0-1】

* **Post‑state caching** – The file also depends on `state/cache/post-shadow` (`src/state/cache/post-shadow.ts`), the module that implements the shadow‑cache for posts. 【get_related_entities†4-5】

Thus, `src/view/com/post/Post.tsx` relies on `useOpenComposer` for opening the composer and on `state/cache/post-shadow` for caching post state.

---
