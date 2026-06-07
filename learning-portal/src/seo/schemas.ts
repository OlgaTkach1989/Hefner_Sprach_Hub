import type { CourseDetail, CourseSummary, Locale } from "../types";

const ORG_NAME = "Learning Hub";

const buildLogoUrl = (siteUrl: string) => `${siteUrl.replace(/\/$/, "")}/logo.svg`;

export const buildOrganizationSchema = (siteUrl: string) => ({
  "@context": "https://schema.org",
  "@type": "Organization",
  name: ORG_NAME,
  url: siteUrl,
  logo: buildLogoUrl(siteUrl),
  areaServed: {
    "@type": "Place",
    name: "International offices"
  },
  address: {
    "@type": "PostalAddress",
    addressLocality: "Berlin",
    addressCountry: "DE"
  }
});

export const buildCourseListSchema = (siteUrl: string, courses: CourseSummary[], locale: Locale) => ({
  "@context": "https://schema.org",
  "@type": "ItemList",
  itemListElement: courses.map((course, index) => ({
    "@type": "ListItem",
    position: index + 1,
    url: `${siteUrl}/course/${course.route_slug ?? course.slug}`,
    item: {
      "@type": "Course",
      name: course.title,
      description: course.short_description,
      provider: {
        "@type": "Organization",
        name: ORG_NAME
      },
      inLanguage: locale === "de" ? "de-DE" : "en-US",
      offers: {
        "@type": "Offer",
        price: course.price_amount,
        priceCurrency: course.currency,
        availability: "https://schema.org/InStock"
      }
    }
  }))
});

export const buildCourseSchema = (siteUrl: string, course: CourseDetail, locale: Locale) => ({
  "@context": "https://schema.org",
  "@type": "Course",
  name: course.title,
  description: course.description,
  provider: {
    "@type": "Organization",
    name: ORG_NAME,
    url: siteUrl
  },
  inLanguage: locale === "de" ? "de-DE" : "en-US",
  offers: {
    "@type": "Offer",
    price: course.price_amount,
    priceCurrency: course.currency,
    availability: "https://schema.org/InStock"
  },
  audience: {
    "@type": "Audience",
    geographicArea: "DE"
  }
});

export const buildFaqSchema = (course: CourseDetail) => ({
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: course.faq_items.map((item) => ({
    "@type": "Question",
    name: item.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: item.answer
    }
  }))
});
