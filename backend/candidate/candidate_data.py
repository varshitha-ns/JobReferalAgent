from candidate.candidate_profile import (
    CandidateProfile,
    Education,
    Experience,
    Project,
    Certification,
    Achievement,
)


candidate_profile = CandidateProfile(
    name="Varshitha N S",
    email="varshithans05@gmail.com",
    phone="+91 7892994179",

    linkedin="https://linkedin.com/in/varshitha-n-s",
    github="https://github.com/varshitha-ns",

    summary=(
        "Computer Science graduate specializing in Artificial Intelligence "
        "and Machine Learning with experience in developing AI-powered "
        "applications using Machine Learning, NLP, Generative AI, RAG, "
        "Agentic AI, and Full-Stack technologies. Passionate about building "
        "scalable, intelligent, and real-world software solutions."
    ),

    education=[
        Education(
            institution="PES College of Engineering, Mandya",
            degree="Bachelor of Engineering",
            specialization="Computer Science (Artificial Intelligence & Machine Learning)",
            graduation_year=2026,
            cgpa=8.91,
        )
    ],

    experience=[
        Experience(
            company="Infosys",
            role="System Engineer Trainee (MERN Stack Intern)",
            start_date="Jan 2026",
            end_date="May 2026",
            description=[
                "Completed training in Java, SQL, DBMS, and the MERN stack "
                "(MongoDB, Express.js, React.js, Node.js).",

                "Developed full-stack web applications, REST APIs, and "
                "JSON-based backend services using MERN technologies.",

                "Worked on requirement analysis, development, testing, "
                "debugging, deployment activities and version control.",

                "Utilized Git, GitHub, Postman, MongoDB Atlas, and VS Code "
                "for collaborative software development.",
            ],
        )
    ],

    projects=[
        Project(
            name="Postpartum Care Platform",
            technologies=[
                "Flask",
                "MongoDB",
                "Machine Learning",
                "DNN",
                "LangChain",
                "RAG",
                "LLM APIs",
                "Embeddings",
                "Vector Retrieval",
            ],
            description=[
                "Designed Flask-based REST APIs with MongoDB to manage "
                "maternal health records and user interactions.",

                "Built machine learning models for postpartum depression "
                "risk prediction, achieving approximately 85–90% validation accuracy.",

                "Implemented DNN-based nutrition recommendations and a "
                "secure RAG-based medical chatbot using LangChain, LLM APIs, "
                "embeddings and vector retrieval.",
            ],
        ),

        Project(
            name="AI-Powered Smart TradeOS Platform",
            technologies=[
                "FastAPI",
                "React",
                "LangChain",
                "Blockchain",
                "Gemini APIs",
                "Agentic AI",
                "RAG",
                "Embeddings",
                "Vector Search",
            ],
            description=[
                "Developed an AI-powered platform for export compliance, "
                "supplier discovery, and trade workflow automation.",

                "Built Agentic AI workflows using LangChain, Gemini APIs, "
                "planning agents, memory, and tool orchestration for "
                "compliance and logistics.",

                "Integrated RAG pipelines with embeddings, vector search, "
                "and blockchain escrow mechanisms for secure trade automation.",
            ],
        ),

        Project(
            name="ML-Powered Consent Engine",
            technologies=[
                "XGBoost",
                "NLP",
                "React",
                "Flask",
                "Androguard",
                "BERT",
            ],
            description=[
                "Developed a machine learning system to analyze Android "
                "APK permissions and classify potential privacy risks "
                "using XGBoost and Androguard.",

                "Applied BERT-based NLP techniques to analyze privacy "
                "policies and identify compliance gaps.",

                "Built a React-Flask application with dashboards to "
                "visualize permission risk scores and compliance insights.",
            ],
        ),
    ],

    programming_languages=[
        "Python",
        "C++",
        "JavaScript",
    ],

    web_backend=[
        "HTML",
        "CSS",
        "React",
        "Express.js",
        "Flask",
        "FastAPI",
        "REST APIs",
    ],

    machine_learning=[
        "PyTorch",
        "NLP",
        "Scikit-learn",
        "Pandas",
        "NumPy",
    ],

    deep_learning=[
        "CNNs",
        "RNNs",
        "Transformers",
        "BERT",
    ],

    generative_ai=[
        "RAG",
        "LangChain",
        "LLM APIs",
        "Agentic AI",
    ],

    databases_tools_cloud=[
        "MongoDB",
        "SQL",
        "Git",
        "GitHub",
        "Postman",
    ],

    cloud_devops=[
        "Docker",
        "Kubernetes",
        "CI/CD",
    ],

    certifications=[
        Certification(
            name="Neural Networks and Deep Learning",
            provider="Coursera",
        ),
        Certification(
            name="Developing Explainable AI (XAI)",
            provider="Coursera",
        ),
        Certification(
            name="Agentic AI and AI Agents",
            provider="Coursera",
        ),
    ],

    achievements=[
        Achievement(
            description="Winner – Tecknothon Hackathon, Tekvocation Mysore."
        ),
        Achievement(
            description="2nd Place – Analytics Arena, IEEE."
        ),
        Achievement(
            description="Best Women Team – Aavishkar Project Expo, SIT Tumkur."
        ),
        Achievement(
            description="Shortlisted among Top 14 teams, Intel AI for Future Workforce Bootcamp."
        ),
    ],

    coding_problems_solved=250,
)