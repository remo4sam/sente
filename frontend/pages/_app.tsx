import type { AppProps } from "next/app";
import Head from "next/head";
import { ClerkProvider } from "@clerk/nextjs";
import type { NextPageWithLayout } from "@/lib/page-types";
import "@/styles/globals.css";

type AppPropsWithLayout = AppProps & {
  Component: NextPageWithLayout;
};

export default function App({ Component, pageProps }: AppPropsWithLayout) {
  const getLayout = Component.getLayout ?? ((page) => page);

  return (
    <ClerkProvider afterSignOutUrl="/" {...pageProps}>
      <Head>
        <title>Sente — Mobile Money Insights</title>
        <meta
          name="description"
          content="AI-powered analyzer for Ugandan mobile money transactions."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      {getLayout(<Component {...pageProps} />)}
    </ClerkProvider>
  );
}
