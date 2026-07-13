# CodeIQ Q&A Agent -- Eval Results

10 questions x 1 models = 10 runs.

## Summary

| Model | Entity-hit rate | Avg latency (s) | Errors | Blank answers | Confidence (H/M/L) |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0.8 | 71.47 | 0 | 0 | 0/7/3 |

## Per-question comparison

### q11: Which component provides the session state to the rest of the app, and where is it defined?

_Expected: The Provider component in src/state/session/index.tsx (lines 105-416) wraps the app in the session StateContext/ApiContext._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 6 retrieved entities scored >=0.6 relevance; top match scored 0.60.) -- entity hit: no -- latency: 52.53s
> The **`Provider` component defined in `src/state/shell/logged-out.tsx`** supplies the session state to the rest of the application. It creates the context that other parts of the app consume (e.g., `StateContext` and `ControlsContext`) and uses the `useSession` hook to obtain the current session information【source:src/state/shell/logged-out.tsx#Provider:72-118】.

---

### q12: There appear to be two different useTheme hooks in the codebase. Where is each defined?

_Expected: src/alf/index.tsx#useTheme (the alf design-system theme hook) and src/lib/ThemeContext.tsx#useTheme (the legacy ThemeContext hook)._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.34.) -- entity hit: yes -- latency: 27.66s
> The codebase contains two distinct **`useTheme`** hooks:

| Hook name | Definition location | Line range |
|-----------|--------------------|------------|
| **`useTheme`** (the simple context hook) | `src/lib/ThemeContext.tsx` | line 92 – 92【src/lib/ThemeContext.tsx:92-92】 |
| **`useTheme`** (the Alf‑specific hook that returns a theme object from the Alf store) | `src/alf/index.tsx` | line 140 – 145【src/alf/index.tsx:140-145】 |

Thus, one `useTheme` is defined in **`ThemeContext.tsx`** as a thin wrapper around `useContext(ThemeContext)`, while the other is defined in **`alf/index.tsx`** and derives the theme from the Alf state via `useAlf` and `useMemo`.

---

### q13: What does the TabsNavigator component in src/Navigation.tsx render?

_Expected: It renders the BottomBar (from view/shell/bottom-bar/BottomBar) and Tab entries defined in the same file._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 4 retrieved entities scored >=0.6 relevance; top match scored 0.56.) -- entity hit: yes -- latency: 97.79s
> The **TabsNavigator** component (defined in `src/Navigation.tsx` lines 582‑617) renders two child components:

* **BottomBar** – the app’s bottom navigation bar.  
* **Tab** – the tab navigator component that provides the tab‑based navigation structure.

These render relationships are shown in the graph data for `TabsNavigator` (`renders: BottomBar, Tab`).

---

### q14: Which tab navigator components does src/Navigation.tsx define?

_Expected: TabsNavigator plus per-tab navigators: HomeTabNavigator, SearchTabNavigator, NotificationsTabNavigator, MyProfileTabNavigator, MessagesTabNavigator, and a FlatNavigator._

**`openai/gpt-oss-120b`** -- confidence: Medium (2 of 8 retrieved entities scored >=0.6 relevance; top match scored 0.63.) -- entity hit: yes -- latency: 119.07s
> `src/Navigation.tsx` defines a **SearchTabNavigator** component, which renders a `SearchTab.Navigator` (see `src/Navigation.tsx#SearchTabNavigator`, lines 659‑669). No other tab‑navigator components are shown in the retrieved evidence.

---

### q15: What breaks if the useAgent hook changes its behavior -- who calls it directly?

_Expected: Direct callers include useFeedFeedback (state/feed-feedback.tsx), useMigrateMutes (state/cache/thread-mutes.tsx), and the app-passwords query/mutation hooks in state/queries/app-passwords.ts._

**`openai/gpt-oss-120b`** -- confidence: Low (0 of 5 retrieved entities scored >=0.6 relevance; top match scored 0.36.) -- entity hit: yes -- latency: 78.05s
> The **`useAgent`** hook is used directly by a handful of other hooks. If its behavior changes, any of those callers will be affected because they rely on the `AtpAgent` instance returned by `useAgent`.

**Direct callers of `useAgent`**

| Caller (hook) | File & line range |
|---------------|-------------------|
| `useFeedFeedback` | `src/state/feed-feedback.tsx:62‑251` |
| `useMigrateMutes` | `src/state/cache/thread-mutes.tsx:58‑104` |
| `useAppPasswordsQuery` | `src/state/queries/app-passwords.ts:10‑20` |
| `useAppPasswordCreateMutation` | `src/state/queries/app-passwords.ts:22‑44` |
| `useAppPasswordDeleteMutation` | `src/state/queries/app-passwords.ts:46‑61` |
| `usePinnedPostMutation` | `src/state/queries/pinned‑post.ts:12‑87` |

These six hooks invoke `useAgent` (as shown by the “Called by” edges in the code graph). Any change to `useAgent`—for example, altering the returned `AtpAgent` instance, throwing different errors, or modifying its side‑effects—could break the functionality of these hooks and, consequently, any UI components or screens that depend on them.

---

### q16: Where is the MessagesScreen defined? Note the file name may not match the screen name.

_Expected: src/screens/Messages/ChatList.tsx#MessagesScreen (lines 82-107) -- the chat-list file defines the MessagesScreen._

**`openai/gpt-oss-120b`** -- confidence: Medium (5 of 5 retrieved entities scored >=0.6 relevance; top match scored 0.64.) -- entity hit: no -- latency: 148.21s
> The model exhausted its tool-call budget before producing a final synthesis. The cited sources below were still retrieved and are valid evidence for this question.

---

### q17: Which screen shows the user's notifications, and which hooks does it call for unread-notification state?

_Expected: NotificationsScreen in src/view/screens/Notifications.tsx, which calls useUnreadNotifications and useUnreadNotificationsApi from state/queries/notifications/unread._

**`openai/gpt-oss-120b`** -- confidence: Medium (3 of 12 retrieved entities scored >=0.6 relevance; top match scored 0.65.) -- entity hit: yes -- latency: 91.72s
> The notifications UI is rendered by **`NotificationsScreen`** (defined in `src/view/screens/Notifications.tsx` lines 49‑170) 【source:src/view/screens/Notifications.tsx:49-170】.  

For the unread‑notification state the screen (and the components it composes) rely on the hooks defined in the notifications query module:

* **`useUnreadNotifications`** – returns the unread‑notifications context 【source:src/state/queries/notifications/unread.tsx#useUnreadNotifications:220-222】  
* **`useUnreadNotificationsApi`** – returns the API helpers for checking unread notifications 【source:src/state/queries/notifications/unread.tsx#useUnreadNotificationsApi:224-226】

These two hooks provide the current unread‑notification count and the function to sync/check it with the server, and are used by the notifications screen to display the user's notifications and indicate unread items.

---

### q18: Which components or screens use the useAccountSwitcher hook?

_Expected: RoutesContainer (src/Navigation.tsx), Deactivated (src/screens/Deactivated.tsx), SwitchAccountDialog (src/components/dialogs/SwitchAccount.tsx), useNotificationsHandler (src/lib/hooks/useNotificationHandler.ts), SettingsScreen (src/screens/Settings/Settings.tsx), and SwitchMenuItem (src/view/shell/desktop/LeftNav.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Medium (0 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.50.) -- entity hit: yes -- latency: 57.42s
> The **useAccountSwitcher** hook is defined in `src/lib/hooks/useAccountSwitcher.ts` (lines 13‑65)【0†L13-L65】.  

No other components, screens, or hooks were shown to call or import this hook in the retrieved graph data. The only related component that appears in the search results is `SwitchAccountDialog` (in `src/components/dialogs/SwitchAccount.tsx`), but its snippet does not indicate that it uses `useAccountSwitcher`; it only shows usage of `useLingui` and other UI elements【2†L15-L65】.  

Therefore, based on the current evidence, **no components or screens have been identified as using the `useAccountSwitcher` hook**.

---

### q19: What does the SearchScreen's file (src/screens/Search/index.tsx) depend on?

_Expected: lib/routes/types and the Search Shell (src/screens/Search/Shell.tsx)._

**`openai/gpt-oss-120b`** -- confidence: Low (No semantically-scored evidence was retrieved for this answer.) -- entity hit: yes -- latency: 27.62s
> The **SearchScreen** file (`src/screens/Search/index.tsx`) has two direct dependencies:

1. **`lib/routes/types`** – a module that provides route‑type definitions.  
2. **`src/screens/Search/Shell.tsx`** – the shell component that implements the screen’s UI and logic.  

These dependencies are shown by the graph edge `depends_on` for the file `src/screens/Search/index.tsx`【src/screens/Search/index.tsx:1-20】【lib/routes/types】【src/screens/Search/Shell.tsx:1-817】.

---

### q20: Is there an internal storybook or developer showcase screen in the app? Where is it defined?

_Expected: Yes -- Storybook, defined in src/view/screens/Storybook/Storybook.tsx (lines 31-160)._

**`openai/gpt-oss-120b`** -- confidence: Medium (1 of 3 retrieved entities scored >=0.6 relevance; top match scored 0.72.) -- entity hit: yes -- latency: 14.62s
> Yes. The app includes an internal **Storybook / developer‑showcase screen**.

* It is exposed as the `StorybookScreen` component, which renders a layout wrapper and lazily loads the actual storybook UI.  
  **Defined in:** `src/view/screens/Storybook/index.tsx` (lines 7‑24)【src/view/screens/Storybook/index.tsx#StorybookScreen】.

* The lazily‑loaded UI itself is the `Storybook` component, which sets theme preferences and renders the storybook UI.  
  **Defined in:** `src/view/screens/Storybook/Storybook.tsx` (lines 31‑160)【src/view/screens/Storybook/Storybook.tsx#Storybook】.

---
