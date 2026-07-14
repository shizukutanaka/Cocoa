import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <>
      <a href="#main-content" className="skip-link">
        本文へスキップ
      </a>
      <header className="app-header">
        <div className="container app-header-inner">
          <NavLink to="/" className="app-logo">
            Cocoa
          </NavLink>
          <nav className="app-nav">
            <NavLink to="/" end>
              マーケットプレイス
            </NavLink>
            <NavLink to="/bundles">バンドル</NavLink>
            {user && <NavLink to="/me/feed">フィード</NavLink>}
            {user && <NavLink to="/collections">コレクション</NavLink>}
            {user && <NavLink to="/me/wishlist">ウィッシュリスト</NavLink>}
            {user && <NavLink to="/cart">カート</NavLink>}
          </nav>
          <div className="app-header-actions">
            {user ? (
              <>
                <NavLink to="/me" className="btn btn-ghost btn-sm">
                  {user.username}
                </NavLink>
                <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
                  ログアウト
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className="btn btn-secondary btn-sm">
                  ログイン
                </NavLink>
                <NavLink to="/register" className="btn btn-primary btn-sm">
                  新規登録
                </NavLink>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="app-main" id="main-content">
        <div className="container">
          <Outlet />
        </div>
      </main>
    </>
  );
}
