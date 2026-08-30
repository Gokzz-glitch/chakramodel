# Machine Learning in Colonoscopy: Deep Extraction

**Assessment of colonoscopy skill using machine learning to measure quality: Proof-of-concept and initial validation**
**Core ML Technology:** Self-supervised vision transformer pre-trained on unlabeled colonoscopy images, fine-tuned for multi-label classification (using a binary threshold of ≥ 0.5) to analyze video frames at 1 frame per second.

## 1. The "Big Picture" & Motivation
* What is the main problem your research is trying to solve?
Measuring colonoscopy quality to reduce the risk of post-colonoscopy colorectal cancer is challenging. Current manual review methods are laborious, suffer from interobserver variation, and barriers like inadequate procedure volume and gamification prevent widespread utility.
* What made you choose this specific topic?
The authors previously found that manual review of colonoscopy videos could estimate quality metrics, but it is too laborious for widespread implementation. They hypothesized that machine learning could assess colonoscopy skill and metrics in an automated fashion.
* Why does this research matter for the industry right now?
An automated, interactive AI assessment can rapidly calculate traditional and novel quality metrics, helping to identify and provide feasible, directed feedback to providers and trainees in need of remediation.

## 2. The Practical Approach (Methodology)
* Are you doing mostly lab experiments, data analysis, or fieldwork?
Data analysis of clinical video data. The study developed and externally validated a machine learning model using stored colonoscopy procedure videos from two affiliated medical centers.
* What framework or formulas are you using to analyze things?
A vision transformer model finetuned for multi-label classification to calculate metrics like insertion time (IT), withdrawal time (WT), polyp detection rate (PDR), polyps per colonoscopy (PPC), high-quality WT (HQ-WT), and withdrawal time minus polypectomy time (WT-PT). Statistical evaluations included Shapiro-Wilk, Kruskal-Wallis, Spearman's rank correlations, and Fisher’s Exact Test.
* How do you usually collect your data or samples?
Videos were automatically uploaded to a cloud server (Virgo Surgical Video Solutions) during procedures and linked with electronic health record data (Epic) and endoscopic reports (Provation).

## 3. Obstacles & Breakthroughs
* What is the biggest challenge you've faced with this project?
Accurately measuring quality metrics automatically, especially handling complexities like excluding polypectomy time from withdrawal time (solved via a novel WT-PT metric) and dealing with inadequate bowel preparation that obscures landmarks.
* Have you hit any dead ends or unexpected results yet?
The AI-CQ overestimated the polyps per colonoscopy (PPC) compared to manual measurement (0.81 vs 0.67) because the model sometimes counted a single polyp twice. Also, in two validation cases, clear cecal landmarks were present but not identified by the model.
* What has been your favorite finding or "eureka" moment?
Creating a web-based, interactive tool that not only calculates overall metrics but presents a timeline of video predictions for landmarks and maneuvers (e.g., retroflexion, cleaning, "red out"), which allows an "expert" and learner to efficiently watch and analyze the video together on demand.

## 4. Lit Review & The "Gap"
* What major gap did you find in the previous research?
While a major focus of colonoscopy AI has been around polyp detection (with multiple commercial products), there has been significantly less work developing algorithms to measure colonoscopy quality and core techniques interactively to provide training feedback.
* Who is the go-to author or foundation paper in your field?
Thakkar et al. are cited for an initial proof of concept on measuring core techniques (cleaning, fold examination). The authors also build on their own prior work regarding feedback on withdrawal and polypectomy techniques.
* Did you find any major contradictions between previous studies?
The authors noted that previous real-time algorithms acting as "speedometers" for withdrawal speed did not actually improve quality, contrasting with their approach of interactive, on-demand video review for directed feedback.

## 5. Future Impact & Advice
* What do you think is the next step for this research area?
Further improvements and additional training of the AI model to ensure reliable routine use, as their initial validation suggests the tool performs well but requires more refinement.
* Where do you see your findings being applied in real life?
In clinical training environments, allowing experts and learners to use AI-augmented video review to efficiently focus on specific procedural areas (like polypectomy or withdrawal technique) for effective feedback and remediation.
* Any tips for someone trying to read papers in this domain?
Look beyond basic polyp detection rates; focus on how AI can qualitatively assess procedural skills (like cleaning and mucosal visibility) and calculate nuanced metrics (like high-quality withdrawal time) to directly improve provider technique.


---

**[Development and Validation of Machine Learning Algorithms for Prediction of Colorectal Polyps Based on Electronic Health Records & 10.3390/biomedicines12091955]**
**Core ML Technology:** Nine machine learning algorithms were evaluated (XGBoost, Logistic Regression, LightGBM, Random Forest, AdaBoost, Decision Tree, Gradient Boosting Decision Tree, Gaussian Naïve Bayes, and Multilayer Perceptron). The final optimal model was AdaBoost (estimators: 50, learning rate: 0.3) built via Python 3.7 using `scikit-learn 1.1.3`, `xgboost 2.0.1`, and `lightgbm 3.2.1`. Feature selection utilized LASSO regression with a binomial setup and 10-fold cross-validation in R. Model interpretability was achieved using the SHAP (SHapley Additive exPlanations) algorithm.

## 1. The "Big Picture" & Motivation
* What is the main problem your research is trying to solve?
Developing a simple, non-invasive, and cost-effective diagnostic prediction model for colorectal polyps using accessible health examination records to identify high-risk asymptomatic individuals, mitigating the general lack of distinctive symptoms of pre-cancerous lesions.
* What made you choose this specific topic?
Colorectal cancer (CRC) is the third most common cancer globally, largely originating from colorectal polyps over a decade. Screening methods like optical colonoscopy and CT colonography are standard but face compliance challenges in the general population due to invasiveness, risks (perforation, bleeding), and high costs.
* Why does this research matter for the industry right now?
It provides an accessible pre-screening risk stratification tool based on routine electronic health records (EHR). This can pinpoint high-risk individuals for targeted colonoscopy, improving screening efficiency while reserving costly and invasive procedures for those who truly need them.

## 2. The Practical Approach (Methodology)
* Are you doing mostly lab experiments, data analysis, or fieldwork?
Data analysis. The research is a single-center observational retrospective study utilizing electronic health examination records.
* What framework or formulas are you using to analyze things?
We utilized a machine learning classification framework. Variables were selected using univariate analysis, binary logistic regression, and LASSO regression with a 10-fold cross-validation L1 penalty. Nine ML classification algorithms were evaluated. Performance was assessed using AUC, accuracy, sensitivity, specificity, predictive values, F1 score, precision-recall (PR) curves, Brier Score, and Decision Curve Analysis (DCA). The SHAP method was used to rank feature importance and visually explain predictions.
* How do you usually collect your data or samples?
Data was extracted from the hospital’s medical database for 5,426 individuals who underwent colonoscopy screening from January 2021 to January 2024. The dataset included demographic data, vital signs, and laboratory results recorded before the first 24 hours post-colonoscopy. The data was split into a 70% training/internal validation set (cohort 1) and a 30% external validation set (cohort 2).

## 3. Obstacles & Breakthroughs
* What is the biggest challenge you've faced with this project?
A major challenge in building ML models on high-dimensional clinical data is avoiding overfitting while maintaining stability. Moreover, a structural limitation of our project was its retrospective, single-center design and the lack of lifestyle data (diet, smoking, alcohol use history) and family history, potentially missing out on significant factors.
* Have you hit any dead ends or unexpected results yet?
During model evaluation, XGBoost exhibited the highest performance in the training set but showed a tendency toward overfitting. AdaBoost was ultimately chosen over XGBoost because it maintained greater stability across both the internal and external validation sets.
* What has been your favorite finding or "eureka" moment?
The AdaBoost model achieved solid predictive performance (AUC 0.675 in external validation) using only 14 non-invasive routine predictors. We were particularly intrigued by identifying novel composite indices like the TyG index (triglyceride glucose index) and NHR (neutrophil count/HDL-C ratio) as significant predictors, underscoring the interaction of chronic inflammation and metabolic immunity in polyp development. Furthermore, we successfully translated the model into a web-based clinical calculator.

## 4. Lit Review & The "Gap"
* What major gap did you find in the previous research?
Prior ML applications for colorectal polyps have heavily relied on costly and invasive procedures like CT colonography and optical colonoscopy images, making them unsuitable for large-scale population screening. Existing non-invasive pre-screening tools often relied on single markers, simple C-statistics, or traditional nomograms (e.g., Lyu Z's model or basic genetic risk scores). There was a lack of predictive models integrating multiple advanced ML ensemble techniques comprehensively analyzing routine clinical and biochemical indicators from EHRs.
* Who is the go-to author or foundation paper in your field?
References to ML in colonoscopy include Wang P et al. (real-time ML colonoscopy detection) and Lawrence EM et al. (CT colonography CAD). For EHR risk stratification, studies by Lyu Z (simple prediction models) and recent ML models incorporating regularized discriminant analysis or neural networks for predicting high-risk polyps were highlighted.
* Did you find any major contradictions between previous studies?
No major contradictions were found. Our findings align strongly with established epidemiological literature indicating that age, sex, obesity (BMI), hyperglycemia, and hyperlipidemia are significant risk factors for colorectal adenomas, while extending these findings via advanced ML interactions.

## 5. Future Impact & Advice
* What do you think is the next step for this research area?
The next step is to conduct broader, multicenter prospective studies to confirm the model's effectiveness and generalizability. Future models should also incorporate missing risk factors (diet, smoking, alcohol, family history), assess specific pathological types of colorectal polyps, and delve deeper into the underlying biological mechanisms.
* Where do you see your findings being applied in real life?
Our model is currently deployed as a web application tool. It is intended to serve as a pre-screening step in health management centers, automatically stratifying asymptomatic patients based on their routine checkup data, and prompting high-risk individuals to undergo formal diagnostic colonoscopies.
* Any tips for someone trying to read papers in this domain?
While not explicitly stated by the authors, readers should focus on how studies select variables from high-dimensional datasets (e.g., LASSO), balance model complexity with stability (e.g., AdaBoost vs. XGBoost), and heavily prioritize model interpretability (using SHAP) to ensure tools are clinically transparent and applicable.


---

**[Colonoscopy polyp classification via enhanced scattering wavelet Convolutional Neural Network (PMC11469526)]**
**Core ML Technology:** Enhanced Scattering Wavelet Convolutional Neural Network (ESWCNN), combining CNNs (utilizing structures from ResNet-50 and ResNet-101) with Scattering Wavelet Transform (SWT) and Discriminant Fast Fourier Transform (FFT) filters. Additional components include PCA for dimensionality reduction and LSTM for temporal sequence analysis. Hardware used: Intel Core-i7-10700K CPU, 32 GB RAM, NVIDIA GeForce RTX 2060 GPU. Hyperparameters: Batch size of 10, learning rate of 0.0003, dropout rate of 0.2, using the SGDM optimizer. 

## 1. The "Big Picture" & Motivation
* **What is the main problem your research is trying to solve?**  
  Our research aims to automate and improve the classification of colorectal polyps to aid in the early detection of colorectal cancer (CRC). We specifically tackle the difficulty of differentiating highly similar polyp classes (e.g., adenoma vs. hyperplastic) under varying colonoscopy lighting and appearance conditions.
* **What made you choose this specific topic?**  
  Colorectal cancer has a significantly high mortality rate, but early polyp removal mitigates this risk. However, up to 3.7% of CRC cases are "interval CRCs" (diagnosed shortly after a normal colonoscopy). This often stems from human endoscopists suffering mental and physical fatigue during prolonged procedures, making an automated "second pair of eyes" crucial. 
* **Why does this research matter for the industry right now?**  
  While Deep Learning is highly effective, deep CNNs easily overfit when trained on the small, labeled datasets typical of the medical domain. Furthermore, training these massive networks is computationally expensive. Our method addresses this by mathematically incorporating scattering wavelets, yielding superior accuracy with significantly fewer learnable parameters and lower hardware constraints.

## 2. The Practical Approach (Methodology)
* **Are you doing mostly lab experiments, data analysis, or fieldwork?**  
  We are doing data analysis on retrospective clinical data. We utilized two public benchmark datasets (PolypGen and GLRC UCI) containing colonoscopy videos and images, as well as one newly curated private clinical dataset (GDZY). 
* **What framework or formulas are you using to analyze things?**  
  We designed the Enhanced Scattering Wavelet Convolutional Neural Network (ESWCNN). It concatenates spatial feature extraction (learnable CNN filters) and spectral feature extraction (invariant scattering wavelet filters and a Discriminant FFT-filter). We balance the CNN and scattering wavelet losses via a dedicated cross-loss function equation, while also applying LSTM to extract temporal features from video sequences.
* **How do you usually collect your data or samples?**  
  Data consists of endoscopic video sequences, including White Light (WL) and Narrow-Band Imaging (NBI) formats. For our private dataset, we also utilized a human weak magnetic signal instrument (MSI) to collect electromagnetic signals before and after polyp resection. We additionally employed Structure-from-Motion (SfM) software to compute dense 3D surface features of the polyps.

## 3. Obstacles & Breakthroughs
* **What is the biggest challenge you've faced with this project?**  
  The primary challenge was dealing with small sample sizes while avoiding model overfitting and immense computational costs. Furthermore, false negatives in cancer screening can lead to misdiagnoses that pose severe risks to patient health, demanding an algorithm that is not just accurate but highly sensitive.
* **Have you hit any dead ends or unexpected results yet?**  
  When testing different modules, we found that despite LSTMs being explicitly designed for temporal sequence data, the combination of LSTM + DWT did not show a comparative advantage over the CNN + DWT combination across our classification metrics. Also, hyperplastic polyps continue to be challenging, as their visual features are frequently confused with adenomas.
* **What has been your favorite finding or "eureka" moment?**  
  Our most significant breakthrough was discovering that our ESWCNN architecture could achieve higher accuracy (96.4% on the UCI dataset) than massively deep state-of-the-art networks like DenseNet-201, while drastically reducing processing time by over 75% (811 seconds vs. 3748 seconds).

## 4. Lit Review & The "Gap"
* **What major gap did you find in the previous research?**  
  Previous models either relied heavily on manual handcrafted features or, when utilizing wavelets alongside CNNs, only used them as preprocessing/postprocessing steps rather than an integrated end-to-end network. Methods that replaced pooling layers with wavelets directly often lost crucial spatial feature information.
* **Who is the go-to author or foundation paper in your field?**  
  Mallat et al. is a foundational reference for our work, as they introduced Scattering Wavelets (ScatNet) that extract translation-invariant features robust to deformations. We also reference the 2015 MICCAI Endoscopic Vision Challenge for early CNN benchmarking.
* **Did you find any major contradictions between previous studies?**  
  While the modern deep learning trend implies that simply increasing network depth (e.g., DenseNet with 201 layers) is the best way to extract deeper features and achieve higher accuracy, our results demonstrate that integrating mathematically structured frequency-domain analysis (wavelets) allows a shallower network to achieve equivalent or superior accuracy much faster.

## 5. Future Impact & Advice
* **What do you think is the next step for this research area?**  
  The next steps involve addressing specific boundary misclassifications—such as distinguishing between hyperplastic and adenomatous lesions—to further minimize false positives and false negatives, ensuring even higher diagnostic reliability.
* **Where do you see your findings being applied in real life?**  
  This technology is primed to be deployed as a real-time Computer-Aided Diagnosis (CAD) system in hospital endoscopy suites, assisting gastroenterologists in real-time by automatically flagging and classifying polyps to reduce human error and fatigue.
* **Any tips for someone trying to read papers in this domain?**  
  You must understand both spatial deep learning (CNNs) and signal processing (Fourier and wavelet transforms). Pay close attention to the evaluation metrics used; because medical datasets suffer from class imbalance, relying solely on standard "accuracy" is misleading, making metrics like the F1-score, sensitivity, and AUC critically important.


---

**Polyp Matching in Colon Capsule Endoscopy: Pioneering CCE-Colonoscopy Integration Towards an AI-Driven Future (DOI: 10.3390/jcm13237034)**
**Core ML Technology:** None directly developed in this study (it is a systematic review). It highlights previous work by Blanes-Vidal et al. using Gower's Similarity Coefficient (GSC) for matching, and notes that no Convolutional Neural Network (CNN)-based algorithms have yet been developed for polyp characterisation in CCE.

## 1. The "Big Picture" & Motivation
* What is the main problem your research is trying to solve?
  The main problem is the duplicate reporting of the same polyp in Colon Capsule Endoscopy (CCE) due to the capsule's rocking motion, leading to an overestimation of polyp numbers and driving the need for unnecessary follow-up colonoscopies.
* What made you choose this specific topic?
  The discrepancy between polyps found in initial CCE and subsequent colonoscopy creates patient anxiety, undermines the cost-effectiveness of CCE, and acts as a major barrier to CCE becoming a widely accepted standard tool alongside conventional colonoscopy.
* Why does this research matter for the industry right now?
  As Artificial Intelligence (AI) advances in CCE, systems will primarily focus on computer-assisted detection. Without accurate polyp matching, presenting clinicians with all detected images could paradoxically increase duplicate reporting and complicate the transition to an AI-assisted workflow.

## 2. The Practical Approach (Methodology)
* Are you doing mostly lab experiments, data analysis, or fieldwork?
  Data analysis. This study is a systematic literature review following PRISMA guidelines to evaluate existing evidence on polyp matching within CCE and between CCE and colonoscopy.
* What framework or formulas are you using to analyze things?
  The Quality Appraisal for Diverse Studies (QuADS) tool was used to assess bias. The review also evaluates the 8-component CCE Polyp Matching (CCE PM) criterion and Gower's Similarity Coefficient (GSC) used in machine learning models to quantify polyp similarity.
* How do you usually collect your data or samples?
  Data was collected through a systematic literature search in EMBASE, MEDLINE, and PubMed (up to September 1, 2024), extracting clinical trials, observational studies, reviews, case series, and editorial letters.

## 3. Obstacles & Breakthroughs
* What is the biggest challenge you've faced with this project?
  The scarcity of research in this niche area (only three directly related studies were found), compounded by inadequate reporting of patient sampling criteria and observer expertise in the existing literature.
* Have you hit any dead ends or unexpected results yet?
  A meta-analysis could not be performed due to the insufficient number of studies. Furthermore, previous machine learning matching attempts showed that around 50% of polyps failed to match due to intrinsic inaccuracies in polyp localisation and sizing between CCE and colonoscopy.
* What has been your favorite finding or "eureka" moment?
  The realization that current CCE workflows are analogous to early paper maps, and the future lies in developing an AI-driven "colon GPS" that automatically tracks and matches polyps across modalities, freeing clinicians to focus purely on therapeutic tasks.

## 4. Lit Review & The "Gap"
* What major gap did you find in the previous research?
  Polyp matching within the same CCE video has been historically underdeveloped and heavily reliant on subjective intuition. Crucially, no CNN-based algorithm has yet been developed specifically for polyp characterisation in CCE.
* Who is the go-to author or foundation paper in your field?
  Blanes-Vidal et al., who pioneered the development of the first machine learning algorithm using Gower’s Similarity Coefficient to match polyps between initial CCE and subsequent colonoscopy.
* Did you find any major contradictions between previous studies?
  Yes, multiple studies consistently show a discrepancy in polyp morphology between modalities; for example, flat polyps in a CO2-inflated colonoscopy often appear polypoidal in a water-submerged, non-insufflated CCE environment.

## 5. Future Impact & Advice
* What do you think is the next step for this research area?
  The next logical step is to improve CCE hardware (image quality) and develop advanced CNN-based AI systems capable of characterising polyps and accurately matching them between CCE and conventional colonoscopy.
* Where do you see your findings being applied in real life?
  These findings can be applied to develop automated AI-assisted "colon GPS" reporting systems that eliminate polyp mismatching, standardise quality assurance, and reduce the burden of unnecessary secondary endoscopies.
* Any tips for someone trying to read papers in this domain?
  Be mindful that polyp appearance and sizing differ significantly depending on the modality (e.g., CCE lacks gas insufflation and uses water immersion). Also, understand that current AI models are mostly geared toward detection (CADe), not characterisation or diagnosis (CADx).


---

