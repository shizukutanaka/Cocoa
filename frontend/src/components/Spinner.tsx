export function Spinner() {
  return <div className="spinner" role="status" aria-label="読み込み中" />;
}

export function CenterSpinner() {
  return (
    <div className="center-loading">
      <Spinner />
    </div>
  );
}
