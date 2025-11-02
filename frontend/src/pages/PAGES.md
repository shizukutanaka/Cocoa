# Frontend Pages Documentation

This document provides an overview of the main page components in the Cocoa frontend.

## `Dashboard.tsx`

**Purpose:**
Serves as the main landing page after a user logs in, providing a summary of key metrics and recent activities.

**Implementation Details:**
- **Layout:** Uses `@atlaskit/page-header` for the page title and primary actions.
- **Data Display:** Key metrics are displayed in custom-styled cards. Recent activities are shown in an `@atlaskit/dynamic-table`.
- **Robustness:** Implements loading and empty states for the activity table.
  - The `isLoading` prop on `DynamicTable` is used to show a loading spinner during data fetching.
  - The `emptyView` prop is used to render an `@atlaskit/empty-state` component when there is no activity data, guiding the user on what to do next.

## `AvatarList.tsx`

**Purpose:**
Displays a list of all avatars created by the user, allowing for management and navigation.

**Implementation Details:**
- **Layout:** Uses `@atlaskit/page-header` and `@atlaskit/dynamic-table`.
- **Robustness:** Similar to the Dashboard, this page implements loading and empty states.
  - The `EmptyState` component includes a primary action button to encourage users to create their first avatar, improving user engagement.

## `AIGenerator.tsx`

**Purpose:**
Allows users to generate custom avatars using AI by selecting various options.

**Implementation Details:**
- **Layout:** A two-column layout separating generation options from the result panel.
- **Forms:** Built using `@atlaskit/form`, with fields for style, complexity, colors, and features. Form controls like `@atlaskit/button` and `@atlaskit/checkbox` are used for a consistent UI.
- **State Management:** Uses a `useReducer` hook to manage the component's complex state (options, generation status, result). This centralizes state logic and makes the component easier to maintain.

## `CollaborationRoom.tsx`

**Purpose:**
Provides a real-time collaborative environment for editing avatars, featuring a 3D viewer and a chat panel.

**Implementation Details:**
- **Layout:** Uses `@atlaskit/page-layout` with `Main` and `RightSidebar` slots to create a clear separation between the main content (viewer) and supplementary tools (participants list, chat).
- **Real-time Communication:** Integrates with `react-use-websocket` to handle real-time messaging.
- **UI Components:** Uses a variety of Atlassian components:
  - `@atlaskit/lozenge` to display connection status.
  - `@atlaskit/avatar` and `@atlaskit/avatar-group` to display participants.
  - `@atlaskit/textfield` and `@atlaskit/button` for the chat input.
- **State Management:** Also refactored to use a `useReducer` hook, which is ideal for managing the various state changes triggered by WebSocket events (new messages, participant updates, etc.).
