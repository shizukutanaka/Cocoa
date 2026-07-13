import { NavLink, Outlet } from "react-router-dom";

const TABS = [
  { to: "/me", label: "プロフィール", end: true },
  { to: "/me/listings", label: "出品管理", end: false },
  { to: "/me/wishlist", label: "ウィッシュリスト", end: false },
  { to: "/me/saved-searches", label: "保存した検索", end: false },
  { to: "/me/orders", label: "注文履歴", end: false },
  { to: "/me/credits", label: "クレジット", end: false },
  { to: "/me/gift-cards", label: "ギフトカード", end: false },
  { to: "/me/referrals", label: "友達を招待", end: false },
  { to: "/me/notifications", label: "通知", end: false },
  { to: "/me/security", label: "セキュリティ", end: false },
];

export function MyPageLayout() {
  return (
    <div className="split-layout">
      <nav className="side-nav">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div>
        <Outlet />
      </div>
    </div>
  );
}
