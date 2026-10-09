import Workspace from "../workspace";

// The shell and its state live in this layout, so they survive navigation between /upload, /search and /search/[studentId].
// The pages below render nothing: the URL only selects which view the workspace shows.
export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <><Workspace />{children}</>;
}
