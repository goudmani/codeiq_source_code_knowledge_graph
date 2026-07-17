# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 1.0 | 45.54 | 0 | 0 | 0/3/7 |

## Per-question comparison

### q11: Which component provides the session state to the rest of the app, and where is it defined?

_Expected: The Provider component in src/state/session/index.tsx (lines 105-416) wraps the app in the session StateContext/ApiContext._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.63.) -- entity hit: yes -- latency: 41.84s
> The **session state** is supplied by the **`Provider` component** that lives in the session state package:

* **Component:** `Provider` (the root provider for the session state)  
* **File / definition:** `src/state/session/index.tsx`, lines 105‑416  

This component creates and renders the `AgentContext`, `StateContext`, `ApiContext` (and the analytics context), making the session information available to the rest of the app【src/state/session/index.tsx#Provider】.

---

### q12: There appear to be two different useTheme hooks in the codebase. Where is each defined?

_Expected: src/alf/index.tsx#useTheme (the alf design-system theme hook) and src/lib/ThemeContext.tsx#useTheme (the legacy ThemeContext hook)._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 25.4s
> The codebase contains two distinct **`useTheme`** hooks:

| Hook name | Definition location | File & line range |
|-----------|--------------------|-------------------|
| **`useTheme`** (the Alf UI hook) | `src/alf/index.tsx` – exported from the Alf package’s entry point. | `src/alf/index.tsx:140‑145` |
| **`useTheme`** (the core theme‑context hook) | `src/lib/ThemeContext.tsx` – defined inside the shared ThemeContext module. | `src/lib/ThemeContext.tsx:92‑92` |

These two hooks are separate implementations: the first is part of the Alf UI layer, while the second lives in the generic theme‑context library.

---

### q13: What does the TabsNavigator component in src/Navigation.tsx render?

_Expected: It renders the BottomBar (from view/shell/bottom-bar/BottomBar) and Tab entries defined in the same file._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 49.01s
> The **TabsNavigator** component (defined in `src/Navigation.tsx:582‑617`) renders the app’s bottom‑tab bar:

* It renders the **BottomBar** component (render call at line 589).  
* Inside the BottomBar it renders a series of **Tab** components (render calls at lines 595, 601‑603, 607 and 611).

So, TabsNavigator’s UI consists of a `BottomBar` that contains several `Tab` elements.  

*Source: `src/Navigation.tsx#TabsNavigator` – renders → `BottomBar` (line 589) and `Tab` (lines 595, 601‑603, 607, 611).*

---

### q14: Which tab navigator components does src/Navigation.tsx define?

_Expected: TabsNavigator plus per-tab navigators: HomeTabNavigator, SearchTabNavigator, NotificationsTabNavigator, MyProfileTabNavigator, MessagesTabNavigator, and a FlatNavigator._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 11.43s
> The **src/Navigation.tsx** file defines the following tab‑navigator components:

| Component | Description (from source) |
|-----------|----------------------------|
| **TabsNavigator** | Native mobile tab‑based navigation container with bottom bar (lines 582‑617) |
| **HomeTabNavigator** | Home tab navigation stack for the main home section (lines 627‑657) |
| **SearchTabNavigator** | Search tab navigation stack for explore and search functionality (lines 659‑669) |
| **NotificationsTabNavigator** | Notifications tab navigation stack for notification management (lines 671‑685) |
| **MyProfileTabNavigator** | Profile tab navigation stack for user profile management (lines 687‑703) |
| **MessagesTabNavigator** | Messages tab navigation stack for chat and messaging features (lines 705‑722) |
| **FlatNavigator** | Web navigation stack for a single flat navigation layout (lines 728‑772) |
| **RoutesContainer** | Main container wrapping all navigation components and handling routing context (lines 852‑1037) |

These definitions are listed under the “defines” relationships for `src/Navigation.tsx`【2†L1-L8】.

---

### q15: What breaks if the useAgent hook changes its behavior -- who calls it directly?

_Expected: Direct callers include useFeedFeedback (state/feed-feedback.tsx), useMigrateMutes (state/cache/thread-mutes.tsx), and the app-passwords query/mutation hooks in state/queries/app-passwords.ts._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 10.23s
> The **useAgent** hook is called directly by the following hooks in the codebase:

| Hook (file) | Lines where it calls `useAgent` |
|-------------|---------------------------------|
| `useFeedFeedback` – **src/state/feed-feedback.tsx** (lines 68) | `src/state/feed-feedback.tsx#useFeedFeedback` |
| `useMigrateMutes` – **src/state/cache/thread-mutes.tsx** (lines 59) | `src/state/cache/thread-mutes.tsx#useMigrateMutes` |
| `useAppPasswordsQuery` – **src/state/queries/app-passwords.ts** (lines 11) | `src/state/queries/app-passwords.ts#useAppPasswordsQuery` |
| `useAppPasswordCreateMutation` – **src/state/queries/app-passwords.ts** (lines 24) | `src/state/queries/app-passwords.ts#useAppPasswordCreateMutation` |
| `useAppPasswordDeleteMutation` – **src/state/queries/app-passwords.ts** (lines 48) | `src/state/queries/app-passwords.ts#useAppPasswordDeleteMutation` |
| `usePinnedPostMutation` – **src/state/queries/pinned-post.ts** (lines 15) | `src/state/queries/pinned-post.ts#usePinnedPostMutation` |

These six hooks directly depend on `useAgent`; any change in `useAgent`’s behavior could affect them. All citations are from the graph edge data showing “calls → in” relationships to `src/state/session/index.tsx#useAgent`.

---

### q16: Where is the MessagesScreen defined? Note the file name may not match the screen name.

_Expected: src/screens/Messages/ChatList.tsx#MessagesScreen (lines 82-107) -- the chat-list file defines the MessagesScreen._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 23.09s
> The **MessagesScreen** component is defined in **`src/screens/Messages/ChatList.tsx`**, spanning lines 82‑107 of that file. 【src/screens/Messages/ChatList.tsx:82-107】

---

### q17: Which screen shows the user's notifications, and which hooks does it call for unread-notification state?

_Expected: NotificationsScreen in src/view/screens/Notifications.tsx, which calls useUnreadNotifications and useUnreadNotificationsApi from state/queries/notifications/unread._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 38.67s
> The **NotificationsScreen** component renders the user’s notifications page.

**Hooks it calls for unread‑notification state**

| Hook | Purpose (as used by the screen) | Call site |
|------|--------------------------------|-----------|
| `useUnreadNotifications` | Retrieves the current unread‑notification count / list from the local query cache | `src/view/screens/Notifications.tsx:53` |
| `useUnreadNotificationsApi` | Provides the API functions to mark notifications as read or fetch fresh unread data | `src/view/screens/Notifications.tsx:55` |

**Evidence**

* The screen definition is in `src/view/screens/Notifications.tsx` (lines 49‑170)【src/view/screens/Notifications.tsx#NotificationsScreen】.  
* Its outgoing “calls” edges list includes `useUnreadNotifications` (line 53) and `useUnreadNotificationsApi` (line 55)【src/view/screens/Notifications.tsx#NotificationsScreen】.

---

### q18: Which components or screens use the useAccountSwitcher hook?

_Expected: RoutesContainer (src/Navigation.tsx), Deactivated (src/screens/Deactivated.tsx), SwitchAccountDialog (src/components/dialogs/SwitchAccount.tsx), useNotificationsHandler (src/lib/hooks/useNotificationHandler.ts), SettingsScreen (src/screens/Settings/Settings.tsx), and SwitchMenuItem (src/view/shell/desktop/LeftNav.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 2 retrieved entities scored >=0.6 relevance; top match scored 0.53.) -- entity hit: yes -- latency: 122.67s
> The **SwitchAccountDialog** component imports and calls `useAccountSwitcher` (see the call listed at line 22 in its definition)【search_code:0】. No other components or screens were found to reference this hook in the retrieved data.

---

### q19: What does the SearchScreen's file (src/screens/Search/index.tsx) depend on?

_Expected: lib/routes/types and the Search Shell (src/screens/Search/Shell.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 70.7s
> The **SearchScreen** file (`src/screens/Search/index.tsx`) has two direct dependencies:

| Dependency | Type | Location |
|------------|------|----------|
| `lib/routes/types` | internal module (no source file listed) | `src/screens/Search/index.tsx` (depends_on) |
| `src/screens/Search/Shell.tsx` | file containing the screen’s component structure and search logic | `src/screens/Search/index.tsx` (depends_on) |

These dependencies are recorded in the graph as outgoing **depends_on** edges from `src/screens/Search/index.tsx`【src/screens/Search/index.tsx:1-20】【src/screens/Search/Shell.tsx:1-817】.

---

### q20: Is there an internal storybook or developer showcase screen in the app? Where is it defined?

_Expected: Yes -- Storybook, defined in src/view/screens/Storybook/Storybook.tsx (lines 31-160)._

**`openai/gpt-oss-120b`** -- confidence: Medium (2 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.66.) -- entity hit: yes -- latency: 62.39s
> Yes. The app includes an internal **Storybook / developer‑showcase screen**.

* The screen entry point is the `StorybookScreen` component, defined in **`src/view/screens/Storybook/index.tsx`** (lines 7‑24)【src/view/screens/Storybook/index.tsx#StorybookScreen】. It wraps the actual Storybook UI in the app’s standard layout.

* The UI that displays the component catalogue is the `Storybook` component, defined in **`src/view/screens/Storybook/Storybook.tsx`** (lines 31‑160)【src/view/screens/Storybook/Storybook.tsx#Storybook】. This component renders the various demo sections (buttons, forms, icons, etc.) used by developers for testing and showcase.

---
