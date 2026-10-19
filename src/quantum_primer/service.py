from .graph import ModelResponder, build_graph


def create_graph(settings):
    if settings.mode == "demo":
        from .demo import DemoResponder, DemoRetriever

        return build_graph(DemoRetriever(), DemoResponder(), mode="demo")
    settings.require_live()
    from .providers import chat
    from .retrieval import HybridRetriever

    retriever = HybridRetriever(settings)
    return build_graph(retriever, ModelResponder(chat(settings)),
                       source_resolver=retriever.named_sources)
