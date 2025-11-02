import React from 'react';
import {
  AtlassianNavigation,
  ProductHome,
  Profile,
  Notifications,
  Settings,
  Help,
} from '@atlaskit/atlassian-navigation';
import { AtlassianIcon } from '@atlaskit/logo';
import Avatar from '@atlaskit/avatar';

const CocoaHome = () => (
  <ProductHome icon={AtlassianIcon} logo={AtlassianIcon} siteTitle="Cocoa" />
);

const ProfileButton = () => (
  <Profile
    icon={<Avatar size="small" />}
    tooltip="ユーザープロファイル"
  />
);

const Header: React.FC = () => {
  return (
    <AtlassianNavigation
      label="header"
      renderProductHome={CocoaHome}
      renderProfile={ProfileButton}
      renderNotifications={() => <Notifications tooltip="通知" />}
      renderSettings={() => <Settings tooltip="設定" />}
      renderHelp={() => <Help tooltip="ヘルプ" />}
    />
  );
};

export default Header;
