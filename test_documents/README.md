# Enterprise IQ test corpus

Synthetic business documents for testing ingestion, search, knowledge-graph relationships, RAG and IQ-level AI queries.
Everything here is fictitious. The corpus is dated **8 Oct 2026** (ISO week 41); the last completed reporting week is
week 40 (28 Sep - 2 Oct 2026). "Visionet" is the services provider whose IQs these are.

**102 documents** across 7 IQs and 7 formats. Each record exists once and is referenced consistently
everywhere: the same account, opportunity, bid, programme, partner and campaign IDs appear in Excel trackers, Word plans,
PDF reports, PowerPoint decks, CSV/JSON system exports and text emails or transcripts.

| IQ | Documents |
| --- | --- |
| Sales (Revenue) IQ | 14 |
| Solutions IQ | 14 |
| Accounts IQ | 16 |
| Channels and Partners IQ | 14 |
| Campaign IQ | 12 |
| Delivery IQ | 20 |
| GTM IQ | 12 |

| Format | Count |  | Classification | Count |
| --- | --- | --- | --- | --- |
| csv | 13 |  | Confidential | 51 |
| docx | 13 |  | Internal | 47 |
| json | 13 |  | Restricted | 2 |
| pdf | 13 |  | Public | 2 |
| pptx | 10 |  |  |  |
| txt | 15 |  |  |  |
| xlsx | 25 |  |  |  |

## Folder structure

```text
test_documents/
  Accounts/account_health/
      Account_Health_Review_Q3_2026.pptx
      Account_Health_Scorecard_Sep_2026.csv
      Northwind_Escalation_Email_Thread_2026-09-29.txt
  Accounts/account_plans/
      Fabrikam_Health_Account_Plan_Summary_FY2027.pdf
      Northwind_Traders_Account_Plan_FY2027.docx
      Woodgrove_Bank_Account_Plan_FY2027.pptx
  Accounts/landscape_whitespace/
      Account_Landscape_and_Whitespace_FY2027.xlsx
  Accounts/meeting_notes/
      Fabrikam_Health_Executive_Meeting_Notes_2026-09-18.docx
      Meridian_Bank_Discovery_Call_Transcript_2026-08-12.txt
      Northwind_Weekly_Sync_Transcript_2026-10-01.txt
      Woodgrove_CDO_Intro_Call_2026-09-09_pasted_notes.txt
      meeting_intel_extracts.json
  Accounts/stakeholder_reports/
      Stakeholder_Map_Key_Accounts_Oct_2026.xlsx
      focusnet_contacts_export_2026-10-06.csv
  Accounts/trigger_events/
      Woodgrove_Bank_Q3_2026_Earnings_Brief.pdf
      external_news_triggers_2026-10.json
  Campaign/account_engagement/
      target_account_engagement_intent_W33-W40.csv
  Campaign/attribution/
      Campaign_Attribution_and_ROI_FY2026.xlsx
  Campaign/campaign_reports/
      BFSI_Webinar_Series_Post_Event_Report.docx
      Marketing_QBR_Q3_2026.pptx
      Q3_2026_Campaign_Performance_Report.pdf
  Campaign/inside_sales/
      Inside_Sales_Activity_Dashboard_W28-W40.xlsx
      Voice_of_Prospect_Digest_September_2026.txt
      hubspot_meetings_export_2026-09.csv
  Campaign/lead_reports/
      MQL_SQL_Funnel_Report_Sep_2026.xlsx
      hubspot_contacts_lifecycle_export_2026-10-01.csv
  Campaign/marketing_data/
      Campaign_Budget_and_Spend_Tracker_2026.xlsx
      hubspot_campaigns_export_2026-10-01.json
  Channels_Partners/deal_registrations/
      Deal_Registration_Tracker_FY2026.xlsx
      aws_ace_opportunities_export_2026-10-05.csv
      microsoft_partner_center_referrals_export_2026-10-05.json
  Channels_Partners/funding/
      Funding_Expiry_Reminder_Lamna_AMM_email.txt
      Microsoft_ECIF_Approval_Woodgrove_POC_email.txt
      Partner_Funding_Tracker_FY2026.xlsx
  Channels_Partners/joint_plans/
      AWS_Partner_Field_Priorities_H2_2026.pdf
      Microsoft_Joint_Business_Plan_FY2027.docx
      joint_account_plans.json
  Channels_Partners/partner_reports/
      Partner_Pipeline_Report_Oct_2026.xlsx
      Partner_Scorecard_Q3_2026.pptx
  Channels_Partners/relationships/
      Microsoft_PDM_Monthly_Sync_Notes_2026-09-24.txt
      Partner_Certifications_Status_Sep_2026.csv
      partner_relationship_map.json
  Delivery/customer_pulse/
      Customer_Pulse_Survey_Responses_Q3_2026.csv
      customer_pulse_summary_Q3_2026.json
  Delivery/emails/
      Atlas_INC-48211_Incident_Report_2026-09-27.txt
      WWI_WMS_SLA_Breach_Notification_2026-10-01.txt
  Delivery/priorities_investments/
      Client_Priorities_and_Future_Investments_FY2027.pdf
  Delivery/programmes/
      Atlas_RAID_Log_W40.xlsx
      PRG-2001_Northwind_Store_Modernisation_Programme_Charter.docx
      Strategic_Programme_Portfolio_Q3_2026.xlsx
  Delivery/qbr_notes/
      Northwind_QBR_Q3_2026_Meeting_Notes.docx
      Relecloud_QBR_Q3_2026_notes.txt
      Wingtip_Logistics_QBR_Q3_2026.pptx
  Delivery/stakeholders/
      Delivery_Stakeholder_Register.xlsx
  Delivery/success_stories/
      Success_Story_Relecloud_AIOps_MTTR.pdf
      Success_Story_Wingtip_Predictive_Maintenance_Pilot.docx
  Delivery/technology_landscape/
      Client_Technology_Landscape_Delivery_View.xlsx
  Delivery/weekly_status/
      Fabrikam_PDP_Weekly_Status_W40_email.txt
      Northwind_Atlas_Weekly_Status_Report_W40.docx
      Wingtip_Fleet_Analytics_Status_W40.pptx
      Woodgrove_Lakehouse_POC_Status_Report_W40.pdf
      delivery_platform_status_feed_W38-W40.json
  GTM/bid_no_bid/
      Calder_Insurance_Go_No-Go_Brief_2026-10-05.docx
      bid_qualification_decisions_FY2026.json
  GTM/bid_performance/
      Bid_Performance_Report_Q3_2026.pdf
  GTM/bid_pipeline/
      Weekly_Bid_Pipeline_Update_W41_email.txt
  GTM/bid_trackers/
      GTM_Bid_Tracker_FY2026.xlsx
      focusnet_bid_register_export_2026-10-06.csv
  GTM/proposals/
      Calder_Insurance_Claims_Modernisation_Proposal_DRAFT_v0.6.docx
      Tailspin_Crew_Ops_Orals_Presentation_2026-09-30.pptx
      Woodgrove_Bank_EDP_RFP_Response_Executive_Summary.pdf
  GTM/win_loss/
      Contoso_Smart_Factory_Bid_Debrief_Transcript_2026-08-21.txt
      Win_Loss_Review_FY2026_YTD.pptx
      win_loss_records_FY2025-FY2026.json
  Sales_Revenue/bookings/
      Bookings_and_New_Logos_FY2026.xlsx
  Sales_Revenue/forecast/
      FY2027_Revenue_Plan_Draft_v0.3.xlsx
      Forecast_Call_Notes_2026-10-05.txt
      Q4_2026_Revenue_Forecast_vs_Actuals.xlsx
  Sales_Revenue/pipeline_reports/
      FocusNet_Pipeline_Report_2026-10-06.xlsx
      pipeline_movement_W40_to_W41.csv
      powerbi_pipeline_dataset_2026-10-06.json
  Sales_Revenue/quota_attainment/
      Quota_and_Attainment_FY2026.xlsx
  Sales_Revenue/renewals/
      Renewals_and_Expansion_Next_180_Days.xlsx
  Sales_Revenue/revenue_reports/
      Monthly_Revenue_Review_Sep_2026.pdf
      Revenue_by_Account_and_Service_Line_FY2025-FY2026.xlsx
      Service_Line_PnL_Q3_2026.xlsx
      SysHCM_revenue_extract_FY26P09.csv
  Sales_Revenue/sales_reviews/
      Sales_QBR_Q3_2026.pptx
  Solutions/analyst_research/
      Analyst_Research_Digest_Q3_2026.docx
  Solutions/capability_gaps/
      accelerator_reuse_log_FY2026.csv
      capability_gaps_and_asset_reuse.json
  Solutions/case_studies/
      Case_Study_Litware_Insurance_Claims_Intake_IDP.docx
      Case_Study_Tailspin_Airlines_AWS_Migration_Factory.pdf
      Case_Study_Wingtip_Logistics_Fleet_Analytics.pdf
      proof_points_and_reference_status.json
  Solutions/pricing/
      Commercial_Pricing_Guidelines_FY2026.pdf
      Pricing_Benchmarks_and_Deal_Pricing_Log_FY2026.xlsx
  Solutions/requirements/
      Calder_Insurance_RFP_Compliance_Matrix_CI-2026-014.xlsx
      RFP_RFI_SOW_Requirement_Patterns_FY2026.csv
  Solutions/solution_documents/
      Cloud_Data_Platform_Reference_Architecture_BFSI.docx
      Solution_Catalogue_by_Service_and_Industry.xlsx
      Win_Themes_Playbook_FY2027.pptx
  _reference/
    entity_master.json      ground truth: every account, contact, opportunity, bid, programme, partner, campaign
    document_index.json     per file: IQ, format, classification, source system, and the IDs it mentions
```

Exclude `_reference/` from ingestion. It is the answer key, not content.

## The cast

IDs match the demo application (`USERS.md`): ACC-1001 Northwind Traders, PRT-01 Microsoft, PRG-2001 Northwind Store
Modernisation, and so on. That means own-scope access tests line up with the demo users (for example `account.owner` sees
only Northwind and Fabrikam; `delivery` sees PRG-2001 and PRG-2002; `alliances` sees Microsoft and AWS).

| Account ID | Account | Industry | Status | Owner | Documents mentioning it |
| --- | --- | --- | --- | --- | --- |
| ACC-1003 | Woodgrove Bank | BFSI | Client | Marcus Bell | 60 |
| ACC-1001 | Northwind Traders | Retail | Client | Priya Raman | 56 |
| ACC-1008 | Wingtip Logistics | Logistics | Client | Sophie Turner | 45 |
| ACC-1002 | Fabrikam Health | Healthcare | Client | Priya Raman | 44 |
| ACC-1009 | Relecloud | Telecom | Client | James Patel | 42 |
| ACC-1010 | Lamna Healthcare | Healthcare | Client | Hannah Lee | 42 |
| ACC-1014 | Calder Insurance | BFSI | Prospect | Marcus Bell | 39 |
| ACC-1004 | Tailspin Airlines | Travel & Transport | Client | Sophie Turner | 38 |
| ACC-1006 | Contoso Manufacturing | Manufacturing | Client | Sophie Turner | 38 |
| ACC-1005 | Litware Insurance | BFSI | Client | Marcus Bell | 37 |
| ACC-1011 | Wide World Importers | Retail | Client | James Patel | 35 |
| ACC-1012 | Trey Research | Life Sciences | Client | Hannah Lee | 35 |
| ACC-1015 | Halcyon Health | Healthcare | Client | Hannah Lee | 35 |
| ACC-1013 | Meridian Bank | BFSI | Prospect | Marcus Bell | 35 |
| ACC-1007 | Adventure Works Retail | Retail | Client | James Patel | 30 |
| ACC-1016 | Alpine Ski House | Hospitality | Client | James Patel | 20 |
| ACC-1017 | Fourth Coffee | Retail | Client | James Patel | 19 |
| ACC-1018 | Proseware Inc | Technology | Client | Hannah Lee | 14 |

Partners: PRT-01 Microsoft, PRT-02 AWS, PRT-03 Databricks, PRT-04 Snowflake, PRT-05 ServiceNow, PRT-06 Guidewire.
Programmes: PRG-2001 to PRG-2007. Campaigns: CMP-2601 to CMP-2608. Systems of record named in the files: FocusNet (CRM),
SysHCM (revenue), HubSpot (marketing), SharePoint, Microsoft Partner Center, AWS Partner Central, Power BI, Copilot transcripts.

## Storylines that cross IQs (good knowledge-graph and multi-hop tests)

1. **Northwind renewal at risk.** Project Atlas (PRJ-3101) turned red in week 39 after 14 stores lost POS on 26 Sep
   (INC-48211). Sponsor Daniel Okafor left on 28 Sep; Sofia Lindqvist started 1 Oct and is meeting Infosys about the AMS
   contract. The AMS renewal (OPP-24101, CTR-7020, $1.45M ACV) is due 1 Feb 2027. Appears in Delivery (status, RAID, QBR,
   incident email), Accounts (plan, transcript, escalation, health), Revenue (forecast risk, margin alert), Campaign (intent
   and SDR notes), Solutions (reference suspended) and Partners (Microsoft loyalty referral expiring).
2. **Meridian Bank pursuit.** Omar Reyes attended the BFSI webinar (CMP-2601) on 22 Jul, became lead LD-30188, then
   OPP-24220 ($2.4M, 58% win odds). The RFP is BID-0614. Microsoft Azure Innovate funding is pending (FND-902), and CFO Grace Liu has never been met.
3. **Woodgrove data platform.** New CDO (Aug), ECIF-funded POC (PRG-2004, FND-901), RFP BID-0612 with BAFO due 14 Oct,
   Q3 earnings announce a $400M technology programme.
4. **Calder Insurance RFP.** Received 5 Oct (BID-0618, $5.8M, 186 requirements: 158 Met, 13 Partial, 15 Gap), first
   Guidewire joint pursuit, AWS MAP incentive, eBook-engaged VP who no-showed an SDR meeting.
5. **Contoso loss.** Lost BID-0597 to Capgemini on price (+14%) and OT references. This links the debrief transcript, win/loss records,
   pricing log, capability gap GAP-031 and the follow-on SAP opportunity (OPP-24141).
6. **Wingtip success.** 7.4% fuel saving, predictive maintenance pilot (-23% roadside breakdowns), EU depots expansion
   (OPP-24171, Databricks registration).
7. **Wide World renewal pressure.** CFO 12% IT cost cut, Wipro ~18% lower, September SLA 97.1% vs 97.5%.

## Sample questions with expected answers

| Question | Expected answer (source) |
| --- | --- |
| Why is the Northwind renewal at risk? | Atlas red since W39 (INC-48211, 14 stores), CSAT 6.1 from 8.4, sponsor exited 28 Sep, Infosys approach; renewal 1 Feb 2027 |
| What is our competitive win rate? | 42% (8 of 19 decided RFP/RFI) - Bid Performance Report Q3 2026 |
| Which campaign sourced the Meridian Bank opportunity? | CMP-2601 BFSI webinar series (lead LD-30188, Omar Reyes) |
| How much partner funding expires in the next 60 days? | $95,000 - Lamna AMM (FND-903), expires 30 Nov 2026 |
| Which deals are stalled? | OPP-24102 Northwind Loyalty Analytics, 55 days without activity |
| What did Contoso say about why we lost? | Price ~14% above Capgemini; OT/plant-floor references; architecture scored highest |
| Which Calder requirements are gaps? | 15 gaps including 088 fixed-price option for phase 1 |
| What is Project Atlas's EAC? | $3.96M cost EAC, +$410K; 92% burn at 78% complete |
| Who is the new decision maker at Northwind? | Sofia Lindqvist, VP Technology from 1 Oct 2026 |
| What did Woodgrove announce in Q3 results? | $400M three-year technology modernisation programme (6 Oct) |

## Access-control test hints

- Documents carry a classification (Public, Internal, Confidential, Restricted) in the file properties and page headers.
- Margin data (`Gross margin %`) is in the revenue workbook and SysHCM extract; per the demo rules only Finance should see it.
- Lead emails appear in the HubSpot exports; per the demo rules only Marketing sees them unmasked.
- `_reference/document_index.json` lists the accounts each file mentions, so own-scope users can be checked
  (for example, `account.owner` should retrieve Northwind and Fabrikam content only).

## How it was made

The corpus was produced by a deterministic Python generator (fixed random seeds) from one shared master-data module, which is
why figures reconcile across files. Excel formulas are stored with their calculated values, so tools that read cached
values (pandas, openpyxl `data_only=True`) see numbers. The generator itself is not part of this folder.
