import "./styles.css";

export const metadata = {
  title: "Approver in the Footer",
  description: "A small model eval about where approval claims come from.",
};

export default function Layout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
