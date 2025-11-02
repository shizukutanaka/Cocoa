import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  SideNavigation,
  NavigationHeader,
  Section,
  NestableNavigationContent,
  ButtonItem,
  Header,
} from '@atlaskit/side-navigation';
import {
  HomeIcon,
  PeopleIcon,
  SettingsIcon,
  QuestionCircleIcon,
  DocumentIcon,
  ActivityIcon,
} from '@atlaskit/icon';
import BitbucketAvatarIcon from '@atlaskit/icon/glyph/bitbucket/avatar';
import JiraSoftwareIcon from '@atlaskit/icon/glyph/jira-software';

const Sidebar: React.FC = () => {
  const location = useLocation();

  return (
    <SideNavigation label="プロジェクトナビゲーション">
      <NavigationHeader>
        <Header>Cocoa</Header>
      </NavigationHeader>
      <NestableNavigationContent initialStack={[]}>
        <Section>
          <ButtonItem
            iconBefore={<HomeIcon label="" />}
            isSelected={location.pathname === '/'}
            linkComponent={p => <Link to="/" {...p} />}
          >
            ダッシュボード
          </ButtonItem>
          <ButtonItem
            iconBefore={<BitbucketAvatarIcon label="" />}
            isSelected={location.pathname.startsWith('/avatars')}
            linkComponent={p => <Link to="/avatars" {...p} />}
          >
            アバター管理
          </ButtonItem>
          <ButtonItem
            iconBefore={<ActivityIcon label="" />}
            isSelected={location.pathname.startsWith('/monitoring')}
            linkComponent={p => <Link to="/monitoring" {...p} />}
          >
            システム監視
          </ButtonItem>
          <ButtonItem
            iconBefore={<PeopleIcon label="" />}
            isSelected={location.pathname.startsWith('/collaboration')}
            linkComponent={p => <Link to="/collaboration" {...p} />}
          >
            コラボレーション
          </ButtonItem>
          <ButtonItem
            iconBefore={<JiraSoftwareIcon label="" />}
            isSelected={location.pathname.startsWith('/ai-generator')}
            linkComponent={p => <Link to="/ai-generator" {...p} />}
          >
            AI生成
          </ButtonItem>
        </Section>
        <Section title="その他">
          <ButtonItem
            iconBefore={<DocumentIcon label="" />}
            isSelected={location.pathname.startsWith('/docs')}
            linkComponent={p => <Link to="/docs" {...p} />}
          >
            ドキュメント
          </ButtonItem>
          <ButtonItem
            iconBefore={<SettingsIcon label="" />}
            isSelected={location.pathname.startsWith('/settings')}
            linkComponent={p => <Link to="/settings" {...p} />}
          >
            設定
          </ButtonItem>
          <ButtonItem
            iconBefore={<QuestionCircleIcon label="" />}
            isSelected={location.pathname.startsWith('/help')}
            linkComponent={p => <Link to="/help" {...p} />}
          >
            ヘルプ
          </ButtonItem>
        </Section>
      </NestableNavigationContent>
    </SideNavigation>
  );
};

export default Sidebar;
