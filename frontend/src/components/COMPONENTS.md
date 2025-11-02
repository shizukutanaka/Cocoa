# Frontend Components Documentation

This document provides an overview of the key UI components in the Cocoa frontend, built with React and the Atlassian Design System.

## Core Layout Components

These components form the main structure of the application layout.

### `Header.tsx`

**Purpose:**
Provides the global top navigation bar for the entire application.

**Implementation Details:**
- Built using `@atlaskit/atlassian-navigation` to ensure a consistent and familiar user experience, mirroring Atlassian's own products.
- It includes a product home button (`ProductHome`) which displays the application's logo and name, and placeholders for user profile, notifications, settings, and help.
- This component is designed to be clean and focused, containing only global actions and information.

**Usage:**
Rendered within the `TopBar` slot of the main `PageLayout` in `App.tsx`.

```tsx
import Header from '@/components/Header';
// ...
<PageLayout>
  <TopBar>
    <Header />
  </TopBar>
  {/* ... */}
</PageLayout>
```

### `Sidebar.tsx`

**Purpose:**
Provides the primary navigation for different sections of the application.

**Implementation Details:**
- Built using `@atlaskit/side-navigation`.
- Integrates with `react-router-dom` for client-side routing. This is achieved by passing the `Link` component from `react-router-dom` to the `linkComponent` prop of each `ButtonItem`.
- This approach is the recommended pattern for integrating routing libraries with Atlassian navigation components, as it avoids manual event handling and improves code clarity.
- The sidebar is organized into logical `Section`s, each containing `ButtonItem`s with appropriate icons from `@atlaskit/icon`.

**Usage:**
Rendered within the `LeftSidebar` slot of the main `PageLayout` in `App.tsx`.

```tsx
import Sidebar from '@/components/Sidebar';
// ...
<PageLayout>
  {/* ... */}
  <Content>
    <LeftSidebar>
      <Sidebar />
    </LeftSidebar>
    {/* ... */}
  </Content>
</PageLayout>
```
